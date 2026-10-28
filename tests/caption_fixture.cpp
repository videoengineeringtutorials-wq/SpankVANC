// Synthetic caption-bearing TS fixture, using the user's CaptionGPT CC encoder.
#include "../native/captions_608.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/opt.h>
}
static void ok(int result) { if (result < 0) throw std::runtime_error("FFmpeg fixture failed"); }
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    AVFormatContext* mux = nullptr;
    ok(avformat_alloc_output_context2(&mux, nullptr, "mpegts", argv[1]));
    AVCodecContext* encoder = avcodec_alloc_context3(avcodec_find_encoder_by_name("libx264"));
    if (!encoder || !mux) return 3;
    encoder->width = 320; encoder->height = 180; encoder->pix_fmt = AV_PIX_FMT_YUV420P;
    encoder->time_base = {1, 25}; encoder->framerate = {25, 1}; encoder->thread_count = 1;
    av_opt_set(encoder->priv_data, "preset", "ultrafast", 0);
    av_opt_set(encoder->priv_data, "a53cc", "1", 0);
    ok(avcodec_open2(encoder, encoder->codec, nullptr));
    AVStream* stream = avformat_new_stream(mux, nullptr);
    ok(avcodec_parameters_from_context(stream->codecpar, encoder));
    stream->time_base = encoder->time_base;
    ok(avio_open(&mux->pb, argv[1], AVIO_FLAG_WRITE));
    ok(avformat_write_header(mux, nullptr));
    AVFrame* frame = av_frame_alloc();
    frame->width = encoder->width; frame->height = encoder->height; frame->format = encoder->pix_fmt;
    ok(av_frame_get_buffer(frame, 32));
    AVPacket* packet = av_packet_alloc();
    CCEncoder caption;
    set_caption(caption, "SPANKVANC CAPTION TEST");
    auto drain = [&] {
        int result;
        while ((result = avcodec_receive_packet(encoder, packet)) >= 0) {
            av_packet_rescale_ts(packet, encoder->time_base, stream->time_base);
            packet->stream_index = stream->index;
            ok(av_interleaved_write_frame(mux, packet));
            av_packet_unref(packet);
        }
        if (result != AVERROR(EAGAIN) && result != AVERROR_EOF) ok(result);
    };
    for (int n = 0; n < 75; ++n) {
        if (n == 40) set_caption(caption, "SECOND CAPTION");
        if (n == 65) set_caption(caption, "\n");
        ok(av_frame_make_writable(frame));
        for (int plane = 0; plane < 3; ++plane) {
            int width = plane ? frame->width / 2 : frame->width;
            int height = plane ? frame->height / 2 : frame->height;
            for (int y = 0; y < height; ++y)
                memset(frame->data[plane] + y * frame->linesize[plane], plane ? 128 : 80 + n, width);
        }
        std::vector<uint8_t> cc;
        build_cc(cc, caption);
        av_frame_remove_side_data(frame, AV_FRAME_DATA_A53_CC);
        auto* side = av_frame_new_side_data(frame, AV_FRAME_DATA_A53_CC, cc.size());
        if (!side) return 4;
        memcpy(side->data, cc.data(), cc.size());
        frame->pts = n;
        ok(avcodec_send_frame(encoder, frame)); drain();
    }
    ok(avcodec_send_frame(encoder, nullptr)); drain();
    ok(av_write_trailer(mux));
    av_packet_free(&packet); av_frame_free(&frame); avcodec_free_context(&encoder);
    avio_closep(&mux->pb); avformat_free_context(mux);
}
