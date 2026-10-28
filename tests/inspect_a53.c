/* Decode actual encoded video and expose its A/53 bytes to the framing checker. */
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <stdio.h>
static void drain(AVCodecContext *dec,AVFrame *frame,int *number) {
    while(avcodec_receive_frame(dec,frame)>=0) {
        AVFrameSideData *cc=av_frame_get_side_data(frame,AV_FRAME_DATA_A53_CC);
        printf("%d ",(*number)++);
        if(cc)for(size_t i=0;i<cc->size;i++)printf("%02x",cc->data[i]);
        puts("");av_frame_unref(frame);
    }
}
int main(int argc,char **argv) {
    AVFormatContext *fmt=NULL;
    if(argc!=2 || avformat_open_input(&fmt,argv[1],NULL,NULL)<0 || avformat_find_stream_info(fmt,NULL)<0)return 1;
    int stream=av_find_best_stream(fmt,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);if(stream<0)return 2;
    const AVCodec *codec=avcodec_find_decoder(fmt->streams[stream]->codecpar->codec_id);
    AVCodecContext *dec=avcodec_alloc_context3(codec);
    if(!dec || avcodec_parameters_to_context(dec,fmt->streams[stream]->codecpar)<0 || avcodec_open2(dec,codec,NULL)<0)return 3;
    AVPacket *pkt=av_packet_alloc();AVFrame *frame=av_frame_alloc();int number=0;
    while(av_read_frame(fmt,pkt)>=0) {
        if(pkt->stream_index==stream) {
            if(avcodec_send_packet(dec,pkt)<0)return 4;
            drain(dec,frame,&number);
        }
        av_packet_unref(pkt);
    }
    avcodec_send_packet(dec,NULL);drain(dec,frame,&number);
    av_frame_free(&frame);av_packet_free(&pkt);avcodec_free_context(&dec);avformat_close_input(&fmt);
    return 0;
}
