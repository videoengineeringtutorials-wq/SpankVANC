// Verify opaque ANC through V210 decode/encode and independent caption removal.
#include "scte_vanc.hpp"
#include <cstring>
#include <iostream>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/frame.h>
#include <libklvanc/vanc.h>
}
int main(){try {
    std::vector<spankvanc::Anc104> anc={{13,0,{0x0c,0xff,0xff,0,12}},{14,0,{0x0a,1,2,3}},{13,0,{0x09,0xff,0x55}}};
    auto blob=spankvanc::pack104(anc);auto same=spankvanc::unpack104(blob.data(),blob.size());
    for(size_t i=0;i<anc.size();++i){
        if(anc[i].line!=same[i].line||anc[i].payload!=same[i].payload)throw std::runtime_error("Opaque ANC changed");
        uint16_t *words=nullptr,count=0;
        if(klvanc_sdi_create_payload(7,0x41,anc[i].payload.data(),anc[i].payload.size(),&words,&count,10))throw std::runtime_error("VANC construction failed");
        if(count!=anc[i].payload.size()+7||!klvanc_checksum_is_valid(words+3,count-3))throw std::runtime_error("Bad VANC checksum");
        for(size_t j=0;j<anc[i].payload.size();++j)if((words[j+6]&255)!=anc[i].payload[j])throw std::runtime_error("VANC payload changed");
        free(words);
    }
    klvanc_context_s *vctx=nullptr;klvanc_line_set_s lines={};
    if(klvanc_context_create(&vctx)||spankvanc::insert104(vctx,&lines,anc))throw std::runtime_error("VANC insertion failed");
    for(int i=0;i<lines.num_lines;++i){
        auto *line=lines.lines[i];
        for(int j=1;j<line->num_entries;++j)if(line->p_entries[j]->h_offset<=line->p_entries[j-1]->h_offset)throw std::runtime_error("Unstable ANC packet order");
        uint16_t *packed=nullptr;int count=0;
        if(klvanc_generate_vanc_line(vctx,line,&packed,&count,1920))throw std::runtime_error("VANC line generation failed");
        free(packed);klvanc_line_free(line);
    }
    klvanc_context_destroy(vctx);
    spankvanc::Bytes command;spankvanc::time33(command,450000,0xfe);
    auto section=spankvanc::section35(6,command);
    spankvanc::Scte35To104 reverse;spankvanc::Scte104Decoder forward;
    auto converted=spankvanc::fragment104(reverse.convert(section,180000));
    auto results=forward.feed(converted[0].payload.data(),converted[0].payload.size(),180000);
    if(results.size()!=1||results[0].section!=section)throw std::runtime_error("SCTE-35 -> 104 timed command roundtrip failed");
    AVCodecContext *enc=avcodec_alloc_context3(avcodec_find_encoder_by_name("v210"));
    AVCodecContext *dec=avcodec_alloc_context3(avcodec_find_decoder(AV_CODEC_ID_V210));
    if(!enc||!dec)throw std::runtime_error("V210 codec unavailable");
    enc->width=dec->width=1280;enc->height=dec->height=720;enc->pix_fmt=AV_PIX_FMT_YUV422P10LE;enc->time_base={1001,60000};
    if(avcodec_open2(enc,enc->codec,nullptr)<0||avcodec_open2(dec,dec->codec,nullptr)<0)throw std::runtime_error("Codec init failed");
    AVFrame *frame=av_frame_alloc(),*decoded=av_frame_alloc();AVPacket *pkt=av_packet_alloc();
    frame->width=enc->width;frame->height=enc->height;frame->format=enc->pix_fmt;
    if(av_frame_get_buffer(frame,32)<0)throw std::bad_alloc();
    for(int i=0;i<3;++i)memset(frame->data[i],0,frame->linesize[i]*frame->height);
    auto *raw=av_frame_new_side_data(frame,AV_FRAME_DATA_SPANKVANC_SCTE104,blob.size());memcpy(raw->data,blob.data(),blob.size());
    auto *cc=av_frame_new_side_data(frame,AV_FRAME_DATA_A53_CC,3);memcpy(cc->data,"\xfc\x94\x20",3);frame->pts=0;
    if(avcodec_send_frame(enc,frame)<0||avcodec_receive_packet(enc,pkt)<0||avcodec_send_packet(dec,pkt)<0||avcodec_receive_frame(dec,decoded)<0)throw std::runtime_error("V210 roundtrip failed");
    raw=av_frame_get_side_data(decoded,AV_FRAME_DATA_SPANKVANC_SCTE104);
    if(!raw||raw->size!=blob.size()||memcmp(raw->data,blob.data(),blob.size()))throw std::runtime_error("SCTE-104 lost through decoder");
    av_frame_remove_side_data(decoded,AV_FRAME_DATA_A53_CC);av_packet_unref(pkt);decoded->pts=1;
    if(avcodec_send_frame(enc,decoded)<0||avcodec_receive_packet(enc,pkt)<0)throw std::runtime_error("V210 re-encode failed");
    size_t size=0;const uint8_t *p=av_packet_get_side_data(pkt,AV_PKT_DATA_SPANKVANC_SCTE104,&size);
    if(!p||size!=blob.size()||memcmp(p,blob.data(),size)||av_packet_get_side_data(pkt,AV_PKT_DATA_A53_CC,nullptr))throw std::runtime_error("Independent SCTE/caption policy failed");
    av_packet_free(&pkt);av_frame_free(&frame);av_frame_free(&decoded);avcodec_free_context(&enc);avcodec_free_context(&dec);
    std::cout<<"Opaque SCTE-104 fragments/lines, VANC checksum, V210 decode/encode, caption strip: PASS\n";
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
