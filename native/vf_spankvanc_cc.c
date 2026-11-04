/* Live 608 CC1 / native 708 Service 1 replacement. Pair journal is private to one route; each output has
 * its own cursor. Never modify source frames or unrelated ANC side data. */
#include <stdio.h>
#include "libavutil/mathematics.h"
#include "libavutil/opt.h"
#include "libavutil/file_open.h"
#include "libavutil/intreadwrite.h"
#include "avfilter.h"
#include "internal.h"
#include "formats.h"
#include "video.h"
#include "spankvanc_cea708_encoder.h"

typedef struct SpankCC {
    const AVClass *class;
    char *journal;
    FILE *file;
    int64_t frame_number;
    int cc_count;
    AVRational field_rate;
    int format;
    int source;
    int cc2;
    Spank708 digital;
} SpankCC;
#define OFFSET(x) offsetof(SpankCC, x)
#define FLAGS AV_OPT_FLAG_FILTERING_PARAM|AV_OPT_FLAG_VIDEO_PARAM
static const AVOption spankvanc_cc_options[] = {
    {"journal", "UTF-8 journal path encoded as hex", OFFSET(journal), AV_OPT_TYPE_STRING, {.str=NULL}, 0, 0, FLAGS},
    {"format", "Generated/output caption format: 608, 708 or both", OFFSET(format), AV_OPT_TYPE_INT, {.i64=1}, 1, 3, FLAGS, .unit="caption_format"},
    {"cea608", "CEA-608 CC1", 0, AV_OPT_TYPE_CONST, {.i64=1}, 0, 0, FLAGS, .unit="caption_format"},
    {"cea708", "Native CEA-708 Service 1", 0, AV_OPT_TYPE_CONST, {.i64=2}, 0, 0, FLAGS, .unit="caption_format"},
    {"both", "CEA-608 CC1 and native CEA-708 Service 1", 0, AV_OPT_TYPE_CONST, {.i64=3}, 0, 0, FLAGS, .unit="caption_format"},
    {"cc2", "Bilingual CC1/CC2 journal; isolate English native Service 1", OFFSET(cc2), AV_OPT_TYPE_BOOL, {.i64=0}, 0, 1, FLAGS},
    {"source", "Select existing output caption types without generating or converting", OFFSET(source), AV_OPT_TYPE_BOOL, {.i64=0}, 0, 1, FLAGS},
    {NULL}
};
AVFILTER_DEFINE_CLASS(spankvanc_cc);
static av_cold int init(AVFilterContext *ctx)
{
    SpankCC *s=ctx->priv;
    char path[4096];
    if (s->source) return 0;
    size_t n=s->journal ? strlen(s->journal) : 0;
    if (!n || n%2 || n/2>=sizeof(path)) return AVERROR(EINVAL);
    for (size_t i=0;i<n/2;i++) {
        unsigned v;
        char pair[3]={s->journal[2*i],s->journal[2*i+1],0};
        if (strspn(pair,"0123456789abcdefABCDEF")!=2 || sscanf(pair,"%x",&v)!=1 || !v)
            return AVERROR(EINVAL);
        path[i]=v;
    }
    path[n/2]=0;
    s->file=avpriv_fopen_utf8(path,"rb");
    if (!s->file) return AVERROR(errno);
    setvbuf(s->file,NULL,_IONBF,0);
    return 0;
}
static av_cold void uninit(AVFilterContext *ctx)
{
    SpankCC *s=ctx->priv;
    if (s->file) fclose(s->file);
}
static int config_input(AVFilterLink *inlink)
{
    SpankCC *s=inlink->dst->priv;
    AVRational rate=inlink->frame_rate;
    if (s->source) return 0;
    /* A/53/CTA-708 transport budget: 600 tuples/second (600000/1001
     * for fractional NTSC rates). 608 fields precede invalid 708 padding. */
    if (!av_cmp_q(rate,(AVRational){24000,1001}) || !av_cmp_q(rate,(AVRational){24,1})) s->cc_count=25;
    else if (!av_cmp_q(rate,(AVRational){25,1})) s->cc_count=24;
    else if (!av_cmp_q(rate,(AVRational){30000,1001}) || !av_cmp_q(rate,(AVRational){30,1})) s->cc_count=20;
    else if (!av_cmp_q(rate,(AVRational){50,1})) s->cc_count=12;
    else if (!av_cmp_q(rate,(AVRational){60000,1001}) || !av_cmp_q(rate,(AVRational){60,1})) s->cc_count=10;
    else {
        av_log(inlink->dst,AV_LOG_ERROR,"Unsupported live caption frame rate %d/%d\n",rate.num,rate.den);
        return AVERROR(EINVAL);
    }
    s->field_rate=rate.den==1001 ? (AVRational){60000,1001} :
        (s->cc_count==24 || s->cc_count==12 ? (AVRational){50,1} : (AVRational){60,1});
    return 0;
}
static int filter_frame(AVFilterLink *inlink, AVFrame *frame)
{
    SpankCC *s=inlink->dst->priv;
    if (s->source) {
        const AVFrameSideData *data=av_frame_get_side_data(frame,AV_FRAME_DATA_A53_CC);
        uint8_t copy[93];
        size_t size;
        if (!data || s->format==3) return ff_filter_frame(inlink->dst->outputs[0],frame);
        size=data->size;
        if (size>sizeof(copy) || size%3) {av_frame_free(&frame);return AVERROR_INVALIDDATA;}
        memcpy(copy,data->data,size);
        for (size_t i=0;i<size;i+=3) {
            int type=copy[i]&3;
            if ((type<2 && s->format==2) || (type>=2 && s->format==1)) {
                copy[i]=type<2 ? (0xf8|type) : 0xfa;
                copy[i+1]=copy[i+2]=type<2 ? 0x80 : 0;
            }
        }
        av_frame_remove_side_data(frame,AV_FRAME_DATA_A53_CC);
        AVFrameSideData *selected=av_frame_new_side_data(frame,AV_FRAME_DATA_A53_CC,size);
        if (!selected) {av_frame_free(&frame);return AVERROR(ENOMEM);}
        memcpy(selected->data,copy,size);
        return ff_filter_frame(inlink->dst->outputs[0],frame);
    }
    uint8_t commands[64]; unsigned command_count=0;
    AVRational time_base=av_inv_q(inlink->frame_rate);
    AVRational field_time=av_inv_q(s->field_rate);
    int64_t first=av_rescale_q_rnd(s->frame_number,time_base,field_time,AV_ROUND_DOWN);
    int64_t last=av_rescale_q_rnd(s->frame_number+1,time_base,field_time,AV_ROUND_DOWN);
    int used=0;
    av_frame_remove_side_data(frame,AV_FRAME_DATA_A53_CC);
    AVFrameSideData *cc=av_frame_new_side_data(frame,AV_FRAME_DATA_A53_CC,s->cc_count*3);
    if (!cc) {av_frame_free(&frame);return AVERROR(ENOMEM);}
    /* Emit on EVERY frame, including silence. At 59.94/60 fps a field-2
     * null slot separates successive field-1 pairs; at 29.97/30 fps both
     * fields are in each frame. Sparse tuples are not broadcast framing. */
    for (int64_t field=first;field<last;field++) {
        uint8_t pair[2]={0x80,0x80};
        if (!(field&1)) {
            long pos=ftell(s->file);
            clearerr(s->file);
            if (fread(pair,1,2,s->file)!=2) {
                pair[0]=pair[1]=0x80;
                if (pos>=0) fseek(s->file,pos,SEEK_SET);
            }
        }
        if (!(field&1) && s->format!=1)
            command_count+=spank708_pair(&s->digital,pair[0],pair[1],commands+command_count);
        cc->data[used*3]=(field&1) ? 0xf9 : (s->format==2 ? 0xf8 : 0xfc);
        if (s->format==2) pair[0]=pair[1]=0x80;
        cc->data[used*3+1]=pair[0];cc->data[used*3+2]=pair[1];
        used++;
    }
    if (command_count) {
        uint8_t digital[51];
        unsigned tuples=spank708_packet(&s->digital,commands,command_count,digital);
        if (!tuples || used+tuples>s->cc_count) {
            av_log(inlink->dst,AV_LOG_ERROR,"CEA-708 packet exceeded frame budget\n");
            av_frame_free(&frame);return AVERROR_INVALIDDATA;
        }
        memcpy(cc->data+used*3,digital,tuples*3);used+=tuples;
    }
    while (used<s->cc_count) {
        cc->data[used*3]=0xfa;cc->data[used*3+1]=cc->data[used*3+2]=0;
        used++;
    }
    s->frame_number++;
    return ff_filter_frame(inlink->dst->outputs[0],frame);
}
static const AVFilterPad inputs[]={ {.name="default",.type=AVMEDIA_TYPE_VIDEO,.filter_frame=filter_frame,.config_props=config_input} };
static const AVFilterPad outputs[]={ {.name="default",.type=AVMEDIA_TYPE_VIDEO} };
const AVFilter ff_vf_spankvanc_cc={
    .name="spankvanc_cc",.description=NULL_IF_CONFIG_SMALL("Replace with continuous field-slotted A/53 captions (608 CC1 / native 708 Service 1)"),
    .priv_size=sizeof(SpankCC),.priv_class=&spankvanc_cc_class,.init=init,.uninit=uninit,
    FILTER_INPUTS(inputs),FILTER_OUTPUTS(outputs),FILTER_QUERY_FUNC(ff_default_query_formats),
    .flags=AVFILTER_FLAG_METADATA_ONLY,
};
