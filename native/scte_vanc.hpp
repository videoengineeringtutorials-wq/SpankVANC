#pragma once
#include "scte35_to104.hpp"
extern "C" {
#include <libklvanc/vanc.h>
#include <libklvanc/vanc-lines.h>
}
namespace spankvanc {
inline int insert104(klvanc_context_s *ctx,klvanc_line_set_s *lines,const std::vector<Anc104>& packets) {
    for(const auto& p:packets){
        uint16_t *words=nullptr,count=0;
        int ret=klvanc_sdi_create_payload(7,0x41,p.payload.data(),p.payload.size(),&words,&count,10);
        if(ret)return ret;
        // libklvanc sorts by horizontal offset. Append after existing entries,
        // giving fragments/cues distinct positions so their order is stable.
        int offset=0;
        for(int i=0;i<lines->num_lines;++i)if(lines->lines[i]->line_number==p.line)
            for(int j=0;j<lines->lines[i]->num_entries;++j){
                auto *entry=lines->lines[i]->p_entries[j];
                offset=std::max(offset,entry->h_offset+entry->pixel_width);
            }
        ret=klvanc_line_insert(ctx,lines,words,count,p.line,offset);
        free(words);if(ret)return ret;
    }
    return 0;
}
}
