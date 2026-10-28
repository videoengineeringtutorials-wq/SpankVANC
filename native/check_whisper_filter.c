/* Run against matching patched FFmpeg and libklvanc; no physical SDI output. */
#include <libavfilter/avfilter.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/buffersink.h>
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libklvanc/vanc.h>
#include <stdio.h>
#include <string.h>
static int cdp_seen, cdp_expected, cdp_error;
static int on_cdp(void *opaque,struct klvanc_context_s *ctx,struct klvanc_packet_eia_708b_s *p) {
    (void)opaque;(void)ctx;
    cdp_seen++;
    if(p->ccdata.cc_count!=cdp_expected || !p->header.caption_service_active || !p->header.ccdata_present) cdp_error=1;
    return 0;
}
static int run(int num,int den,int count) {
    const char *name="whisper-filter-test.pairs";
    FILE *f=fopen(name,"wb");
    uint8_t pairs[]={0x94,0x25,0x94,0x25,0xc8,0x49,0x94,0xad};
    if (!f) return 1;
    fwrite(pairs,1,sizeof(pairs),f);fclose(f);
    char hex[256]={0},args[512];
    for(size_t i=0;i<strlen(name);i++) sprintf(hex+2*i,"%02x",(unsigned char)name[i]);
    AVFilterGraph *g=avfilter_graph_alloc();AVFilterContext *src,*cc,*sink;
    snprintf(args,sizeof(args),"video_size=64x64:pix_fmt=%d:time_base=%d/%d:pixel_aspect=1/1:frame_rate=%d/%d",AV_PIX_FMT_YUV422P10LE,den,num,num,den);
    if(avfilter_graph_create_filter(&src,avfilter_get_by_name("buffer"),"src",args,NULL,g)<0)return 2;
    snprintf(args,sizeof(args),"journal=%s",hex);
    if(avfilter_graph_create_filter(&cc,avfilter_get_by_name("spankvanc_cc"),"cc",args,NULL,g)<0)return 3;
    if(avfilter_graph_create_filter(&sink,avfilter_get_by_name("buffersink"),"sink",NULL,NULL,g)<0)return 4;
    if(avfilter_link(src,0,cc,0)<0 || avfilter_link(cc,0,sink,0)<0 || avfilter_graph_config(g,NULL)<0)return 5;
    AVCodecContext *enc=avcodec_alloc_context3(avcodec_find_encoder_by_name("v210"));
    enc->width=enc->height=64;enc->pix_fmt=AV_PIX_FMT_YUV422P10LE;enc->time_base=(AVRational){den,num};
    if(avcodec_open2(enc,enc->codec,NULL)<0)return 6;
    struct klvanc_context_s *vctx=NULL;
    if(klvanc_context_create(&vctx))return 7;
    struct klvanc_callbacks_s callbacks={.eia_708b=on_cdp};vctx->callbacks=&callbacks;
    int found=0;int64_t field_index=0;
    for(int i=0;i<40;i++) {
        /* Appending an incomplete pair must not lose its first byte at EOF. */
        if(i==20 || i==22) {f=fopen(name,"ab");if(!f)return 8;fwrite(pairs+(i==20?0:1),1,1,f);fclose(f);}
        AVFrame *in=av_frame_alloc(),*out=av_frame_alloc();
        in->width=in->height=64;in->format=enc->pix_fmt;in->pts=i;
        if(av_frame_get_buffer(in,32)<0)return 9;
        AVFrameSideData *old=av_frame_new_side_data(in,AV_FRAME_DATA_A53_CC,3);memset(old->data,0xff,3);
        av_dict_set(&in->metadata,"independent","retained",0);
        if(av_buffersrc_add_frame_flags(src,in,AV_BUFFERSRC_FLAG_KEEP_REF)<0 || av_buffersink_get_frame(sink,out)<0)return 10;
        AVFrameSideData *data=av_frame_get_side_data(out,AV_FRAME_DATA_A53_CC);
        if(!data || data->size!=count*3)return 11;
        /* Independent budget/field cadence check, including silence frames. */
        int fields=num==24000 || num==24 ? (i%2 ? 3:2) : (num/den<=30 ? 2:1);
        for(int j=0;j<count;j++) {
            uint8_t *v=data->data+j*3;
            if(j>=fields) {if(v[0]!=0xfa || v[1] || v[2])return 12;continue;}
            if(field_index++%2) {if(v[0]!=0xf9 || v[1]!=0x80 || v[2]!=0x80)return 13;}
            else {
                if(v[0]!=0xfc || !(__builtin_popcount(v[1])%2) || !(__builtin_popcount(v[2])%2))return 14;
                if(v[1]!=0x80 || v[2]!=0x80) {
                    int at=found<4 ? found*2:0;
                    if(found>=5 || memcmp(v+1,pairs+at,2))return 15;
                    found++;
                }
            }
        }
        if(!av_dict_get(out->metadata,"independent",NULL,0) || av_frame_get_side_data(in,AV_FRAME_DATA_A53_CC)->data[0]!=0xff)return 16;
        /* Actual V210 packet side data, then the same CDP builder as SDI muxer. */
        AVPacket *pkt=av_packet_alloc();
        if(avcodec_send_frame(enc,out)<0 || avcodec_receive_packet(enc,pkt)<0)return 17;
        size_t size=0;const uint8_t *raw=av_packet_get_side_data(pkt,AV_PKT_DATA_A53_CC,&size);
        if(!raw || size!=data->size || memcmp(raw,data->data,size))return 18;
        struct klvanc_packet_eia_708b_s *cdp=NULL;
        if(klvanc_create_eia708_cdp(&cdp) || klvanc_set_framerate_EIA_708B(cdp,den,num))return 19;
        cdp->header.ccdata_present=cdp->header.caption_service_active=1;cdp->ccdata.cc_count=count;
        for(int j=0;j<count;j++) {
            cdp->ccdata.cc[j].cc_valid=(raw[j*3]&4)!=0;cdp->ccdata.cc[j].cc_type=raw[j*3]&3;
            memcpy(cdp->ccdata.cc[j].cc_data,raw+j*3+1,2);
        }
        klvanc_finalize_EIA_708B(cdp,i);
        uint16_t *words=NULL,nwords=0;uint8_t *bytes=NULL;uint16_t nbytes=0;
        if(klvanc_convert_EIA_708B_to_words(cdp,&words,&nwords) || klvanc_convert_EIA_708B_to_packetBytes(cdp,&bytes,&nbytes))return 20;
        unsigned sum=0;for(int j=0;j<nbytes;j++)sum+=bytes[j];
        if((sum&255) || !klvanc_checksum_is_valid(words+3,nwords-3))return 21;
        cdp_expected=count;int before=cdp_seen;
        if(klvanc_packet_parse(vctx,11,words,nwords)<0 || cdp_seen!=before+1 || cdp_error)return 22;
        free(bytes);free(words);klvanc_destroy_eia708_cdp(cdp);av_packet_free(&pkt);
        av_frame_free(&in);av_frame_free(&out);
    }
    klvanc_context_destroy(vctx);avcodec_free_context(&enc);avfilter_graph_free(&g);remove(name);
    if(found!=5)return 23;
    printf("%d/%d fps: continuous %d-tuple A/53, fields, parity, V210/CDP/VANC checksums: PASS\n",num,den,count);
    return 0;
}
int main(void) {
    int rates[][3]={{30000,1001,20},{30,1,20},{60000,1001,10},{60,1,10},{25,1,24},{50,1,12},{24000,1001,25},{24,1,25}};
    for(unsigned i=0;i<sizeof(rates)/sizeof(rates[0]);i++) {
        int r=run(rates[i][0],rates[i][1],rates[i][2]);
        if(r){printf("FAIL %d/%d: %d\n",rates[i][0],rates[i][1],r);return r;}
    }
    return 0;
}
