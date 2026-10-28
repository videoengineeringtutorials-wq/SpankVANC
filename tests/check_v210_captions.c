/* Run against the locally patched FFmpeg; no DeckLink hardware required. */
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <string.h>
#include <stdio.h>
int main(void) {
    const uint8_t captions[] = {0xfc, 0x94, 0x20, 0xfe, 0x01, 0x02, 0xff, 0x03, 0x04};
    AVCodecContext *ctx = avcodec_alloc_context3(avcodec_find_encoder_by_name("v210"));
    AVFrame *frame = av_frame_alloc();
    AVPacket *pkt = av_packet_alloc();
    if (!ctx || !frame || !pkt) return 1;
    ctx->width = 1280; ctx->height = 720; ctx->pix_fmt = AV_PIX_FMT_YUV422P10LE;
    ctx->time_base = (AVRational){1001, 60000};
    if (avcodec_open2(ctx, ctx->codec, NULL) < 0) return 2;
    frame->width = ctx->width; frame->height = ctx->height; frame->format = ctx->pix_fmt;
    if (av_frame_get_buffer(frame, 32) < 0) return 3;
    for (int i = 0; i < 3; i++) memset(frame->data[i], 0, frame->linesize[i] * frame->height);
    for (int strip = 0; strip < 2; strip++) {
        AVFrameSideData *sd = av_frame_new_side_data(frame, AV_FRAME_DATA_A53_CC, sizeof(captions));
        if (!sd) return 4;
        memcpy(sd->data, captions, sizeof(captions));
        if (strip) av_frame_remove_side_data(frame, AV_FRAME_DATA_A53_CC);
        frame->pts = strip;
        if (avcodec_send_frame(ctx, frame) < 0 || avcodec_receive_packet(ctx, pkt) < 0) return 5;
        size_t size = 0;
        const uint8_t *cc = av_packet_get_side_data(pkt, AV_PKT_DATA_A53_CC, &size);
        if (strip ? cc != NULL : !cc || size != sizeof(captions) || memcmp(cc, captions, size)) return 6;
        av_packet_unref(pkt);
    }
    av_packet_free(&pkt); av_frame_free(&frame); avcodec_free_context(&ctx);
    puts("V210 608/708 side-data pass and strip: PASS");
    return 0;
}
