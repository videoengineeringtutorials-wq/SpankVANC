// SCTE-35 program commands to SCTE-104 MOMs; no SDK/FFmpeg dependency.
#pragma once
#include "scte104.hpp"
namespace spankvanc {
struct Anc104 { uint16_t line=13; uint8_t stream=0; Bytes payload; };
inline std::vector<Anc104> fragment104(const Bytes& message,uint16_t line=13) {
    if(message.empty()||message.size()>2000||line==0||line>2047)throw std::runtime_error("Invalid SCTE-104 message/line");
    std::vector<Anc104> out;
    for(size_t pos=0;pos<message.size();pos+=254){
        size_t end=std::min(pos+254,message.size());
        Bytes p={uint8_t(8|(pos?2:0)|(end<message.size()?4:0))};
        p.insert(p.end(),message.begin()+pos,message.begin()+end);
        if (size_t(line)+out.size()>2047) throw std::runtime_error("SCTE-104 fragment line overflow");
        out.push_back({uint16_t(line+out.size()),0,std::move(p)});
    }
    return out;
}
// Private, versioned frame side data. Exact ST 2010 bytes and original line
// are retained; no reassembly or command decoding occurs for SDI pass.
inline Bytes pack104(const std::vector<Anc104>& packets) {
    if(packets.size()>128)throw std::runtime_error("SCTE-104 ANC packet limit");
    Bytes b={'S','1','0','4',1,uint8_t(packets.size())};
    for(const auto& p:packets){
        if(p.stream||!p.line||p.line>2047||p.payload.empty()||p.payload.size()>255)
            throw std::runtime_error("SCTE-104 requires primary SDI stream, valid VANC line and 1..255 payload bytes");
        put16(b,p.line);b.push_back(p.stream);b.push_back(p.payload.size());
        b.insert(b.end(),p.payload.begin(),p.payload.end());
    }
    return b;
}
inline std::vector<Anc104> unpack104(const uint8_t* data,size_t n) {
    if(n<6||n>6+128*259||data[0]!='S'||data[1]!='1'||data[2]!='0'||data[3]!='4'||data[4]!=1||data[5]>128)
        throw std::runtime_error("Invalid SCTE-104 frame data");
    std::vector<Anc104> out;size_t j=6;
    for(unsigned i=0;i<data[5];++i){
        if(j+4>n)throw std::runtime_error("Truncated SCTE-104 ANC header");
        Anc104 p;p.line=(data[j]<<8)|data[j+1];p.stream=data[j+2];size_t len=data[j+3];j+=4;
        if(!p.line||p.line>2047||p.stream||!len||j+len>n)throw std::runtime_error("Invalid SCTE-104 ANC record");
        p.payload.assign(data+j,data+j+len);j+=len;out.push_back(std::move(p));
    }
    if(j!=n)throw std::runtime_error("Trailing SCTE-104 ANC bytes");
    return out;
}
class Scte35To104 {
    uint8_t message_number=0;
    std::map<Bytes,int64_t> seen;
public:
    Bytes convert(const Bytes& s,int64_t frame90k) {
        auto error=[](const char* text){throw std::runtime_error(text);};
        if(s.size()<20||s.size()>4096||s[0]!=0xfc||(s[1]&0xf0)!=0x30||((size_t(s[1]&15)<<8)|s[2])+3!=s.size()||crc_mpeg(s.data(),s.size()))error("Invalid SCTE-35 section length/CRC");
        if(s[3]||(s[4]&0xfe))error("Encrypted/unsupported SCTE-35 protocol");
        if(((s[10]<<4)|(s[11]>>4))!=0xfff)error("Non-default SCTE-35 tier is not supported");
        for(auto it=seen.begin();it!=seen.end();)if(frame90k<it->second||frame90k-it->second>=450000)it=seen.erase(it);else ++it;
        if(s[13] && seen.count(s))return {};
        uint64_t adjust=(uint64_t(s[4]&1)<<32)|(uint64_t(s[5])<<24)|(uint64_t(s[6])<<16)|(s[7]<<8)|s[8];
        size_t declared=((s[11]&15)<<8)|s[12],pos=14,limit=s.size()-4;
        auto u8=[&]()->uint8_t{if(pos>=limit)error("Truncated SCTE-35 command");return s[pos++];};
        auto u16=[&](){uint16_t a=u8();return uint16_t((a<<8)|u8());};
        auto u32=[&](){uint32_t a=u16();return (a<<16)|u16();};
        auto ticks33=[&](uint8_t first){uint64_t low=u32();return (uint64_t(first&1)<<32)|low;};
        auto preroll=[&](uint64_t target){
            uint64_t distance=(target+adjust-uint64_t(frame90k))&pts_mask;
            if(distance>(uint64_t(1)<<32))error("Late SCTE-35 target; cue rejected");
            uint64_t ms=(distance+45)/90;
            if(ms>65535)error("SCTE-35 preroll exceeds SCTE-104 65535 ms limit");
            return uint16_t(ms);
        };
        auto time=[&](){uint8_t flags=u8();if(!(flags&0x80))error("Unspecified SCTE-35 splice_time is unsupported");return ticks33(flags);};
        Bytes body;uint16_t op=0;
        if(s[13]==0){op=0x0102;}
        else if(s[13]==6){op=0x0104;uint64_t target=time();put16(body,preroll(target));}
        else if(s[13]==5){
            op=0x0101;uint32_t event=u32();bool cancel=u8()&0x80;
            uint8_t kind=5,avail=0,expected=0,auto_return=0;uint16_t program=0,pre=0,duration=0;
            if(!cancel){
                uint8_t flags=u8();bool out=flags&0x80,has_duration=flags&0x20,immediate=flags&0x10;
                if(!(flags&0x40))error("Component SCTE-35 splices are unsupported");
                kind=out?(immediate?2:1):(immediate?4:3);
                if(!immediate){uint64_t target=time();pre=preroll(target);}
                if(has_duration){
                    uint8_t f=u8();auto_return=bool(f&0x80);uint64_t ticks=ticks33(f);
                    if(!out)error("Duration on a splice-end command is unsupported");
                    if(ticks%9000||ticks/9000>65535||!ticks)error("Break duration must fit SCTE-104 0.1-second units");
                    duration=ticks/9000;
                }
                program=u16();avail=u8();expected=u8();
            }
            body.push_back(kind);put32(body,event);put16(body,program);put16(body,pre);put16(body,duration);
            body.push_back(avail);body.push_back(expected);body.push_back(auto_return);
        }else error("Unsupported SCTE-35 command (program splice_insert/time_signal/splice_null only)");
        if(declared!=0xfff && pos!=14+declared)error("SCTE-35 command length mismatch");
        size_t desc_len=u16(),start=pos,end=pos+desc_len;unsigned count=0;
        if(end>limit)error("Truncated SCTE-35 descriptor loop");
        while(pos<end){if(pos+2>end||pos+2+s[pos+1]>end)error("Invalid SCTE-35 descriptor length");pos+=2+s[pos+1];if(++count>255)error("Too many SCTE-35 descriptors");}
        while(pos<limit)if(u8()!=0xff)error("Invalid SCTE-35 alignment stuffing");
        Bytes m={0xff,0xff,0,0,0,0,message_number,0,0,0,0,uint8_t(count?2:1)};
        put16(m,op);put16(m,body.size());m.insert(m.end(),body.begin(),body.end());
        if(count){put16(m,0x0108);put16(m,desc_len+1);m.push_back(count);m.insert(m.end(),s.begin()+start,s.begin()+end);}
        if(m.size()>2000)error("SCTE-104 message exceeds ST 2010 fragment limit");
        m[2]=m.size()>>8;m[3]=m.size();
        if(seen.size()>=4096)error("SCTE-35 duplicate cache limit");
        if(s[13])seen[s]=frame90k;
        ++message_number;return m;
    }
};
}
