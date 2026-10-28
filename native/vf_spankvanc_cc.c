/* Live CC1 replacement. Pair journal is private to one route; each output has
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

typedef struct SpankCC {
    const AVClass *class;
    char *journal;
    FILE *file;
    int64_t frame_number;
    int cc_count;
    AVRational field_rate;
} SpankCC;
#define OFFSET(x) offsetof(SpankCC, x)
#define FLAGS AV_OPT_FLAG_FILTERING_PARAM|AV_OPT_FLAG_VIDEO_PARAM
static const AVOption spankvanc_cc_options[] = {
    {"journal", "UTF-8 journal path encoded as hex", OFFSET(journal), AV_OPT_TYPE_STRING, {.str=NULL}, 0, 0, FLAGS},
    {NULL}
};
AVFILTER_DEFINE_CLASS(spankvanc_cc);
static av_cold int init(AVFilterContext *ctx)
{
    SpankCC *s=ctx->priv;
    char path[4096];
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
        cc->data[used*3]=(field&1) ? 0xf9 : 0xfc;
        cc->data[used*3+1]=pair[0];cc->data[used*3+2]=pair[1];
        used++;
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
    .name="spankvanc_cc",.description=NULL_IF_CONFIG_SMALL("Replace with continuous field-slotted A/53 CC1 captions"),
    .priv_size=sizeof(SpankCC),.priv_class=&spankvanc_cc_class,.init=init,.uninit=uninit,
    FILTER_INPUTS(inputs),FILTER_OUTPUTS(outputs),FILTER_QUERY_FUNC(ff_default_query_formats),
    .flags=AVFILTER_FLAG_METADATA_ONLY,
};
