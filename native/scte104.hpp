// SpankVANC SCTE-104 program-splice subset and ST 2010 reassembly.
// Independent of DeckLink/FFmpeg. Time type 0 uses the containing source frame.
#pragma once
#include <cstdint>
#include <vector>
#include <map>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <atomic>
namespace spankvanc {
using Bytes = std::vector<uint8_t>;
constexpr uint64_t pts_mask = (uint64_t(1)<<33)-1;
inline uint32_t crc_mpeg(const uint8_t* p, size_t n) {
    uint32_t c=0xffffffff;
    while(n--) { c ^= uint32_t(*p++)<<24; for(int i=0;i<8;++i)c=(c<<1)^((c&0x80000000)?0x04c11db7:0); }
    return c;
}
inline void put16(Bytes& b,uint16_t v){b.push_back(v>>8);b.push_back(v);}
inline void put32(Bytes& b,uint32_t v){b.push_back(v>>24);b.push_back(v>>16);b.push_back(v>>8);b.push_back(v);}
inline uint16_t get16(const Bytes& b,size_t p){if(p+2>b.size())throw std::runtime_error("Truncated SCTE-104 field");return (b[p]<<8)|b[p+1];}
inline void time33(Bytes& b,uint64_t p,uint8_t flags){p&=pts_mask;b.push_back(flags|uint8_t(p>>32));put32(b,uint32_t(p));}
inline Bytes section35(uint8_t type,const Bytes& command,const Bytes& descriptors={}) {
    Bytes b={0xfc,0x30,0,0,0,0,0,0,0,0,0xff,uint8_t(0xf0|(command.size()>>8)),uint8_t(command.size()),type};
    b.insert(b.end(),command.begin(),command.end());put16(b,descriptors.size());b.insert(b.end(),descriptors.begin(),descriptors.end());
    size_t len=b.size()+4-3;if(len>4093)throw std::runtime_error("SCTE-35 section too long");b[1]|=len>>8;b[2]=len;put32(b,crc_mpeg(b.data(),b.size()));return b;
}
struct ScteResult { Bytes section; uint32_t event_id=0; uint8_t type=0; uint64_t target=0; bool internal_heartbeat=false; };
class Scte104Decoder {
    struct Fragment{Bytes bytes;int64_t first=0;unsigned count=0;};
    std::map<uint32_t,Fragment> fragments;
    std::map<Bytes,int64_t> seen;
    std::map<uint32_t,std::pair<Bytes,int64_t>> last_packets;
public:
    std::atomic<bool> failed{false};
    uint64_t rejected = 0;
    std::string last_error, last_payload_hex;
    int64_t last_rejected_pts = 0;
    std::vector<ScteResult> consume(const uint8_t* p,size_t n,int64_t pts,uint32_t stream=0,bool strict=false) {
        if(failed.load())return {};
        try { return feed(p,n,pts,stream); }
        catch(const std::bad_alloc&) { failed.store(true); throw; }
        catch(const std::exception& error) {
            ++rejected;last_error=std::string(error.what()).substr(0,512);last_rejected_pts=pts;
            last_payload_hex.clear();const char *hex="0123456789abcdef";
            for(size_t i=0;i<std::min(n,size_t(255));++i){last_payload_hex+=hex[p[i]>>4];last_payload_hex+=hex[p[i]&15];}
            // Discard only this stream's incomplete message. Keep valid cue dedupe state.
            fragments.erase(stream);last_packets.erase(stream);
            if(strict)failed.store(true);
            return {};
        }
    }

    std::vector<ScteResult> feed(const uint8_t* p,size_t n,int64_t pts,uint32_t stream=0) {
        if(n<2||n>255)throw std::runtime_error("Invalid ST 2010 packet size");
        uint8_t flags=p[0];if((flags&0xf8)!=8)throw std::runtime_error("Unsupported ST 2010 payload version/reserved bits");
        Bytes normalized(p,p+n);normalized[0]&=0xfe;
        auto previous=last_packets.find(stream);
        if((flags&1) && previous!=last_packets.end() && previous->second.first==normalized &&
           pts>=previous->second.second && pts-previous->second.second<90000)return {};
        if(last_packets.size()>=16 && !last_packets.count(stream))last_packets.erase(last_packets.begin());
        last_packets[stream]={normalized,pts};
        bool more=flags&4,following=flags&2;
        auto it=fragments.find(stream);
        if(it!=fragments.end() && (pts-it->second.first>90000||pts<it->second.first)){fragments.erase(it);it=fragments.end();}
        Bytes message;
        if(!following){
            fragments.erase(stream);
            if(more){if(fragments.size()>=16)throw std::runtime_error("ST 2010 fragment stream limit");fragments[stream]={Bytes(p+1,p+n),pts,1};return {};}
            message.assign(p+1,p+n);
        }else{
            if(it==fragments.end())throw std::runtime_error("Orphan/expired ST 2010 following fragment");
            auto& f=it->second;
            if(++f.count>16||f.bytes.size()+n-1>2000){fragments.erase(it);throw std::runtime_error("ST 2010 fragment size/count limit");}
            f.bytes.insert(f.bytes.end(),p+1,p+n);
            if(more)return {};
            message=std::move(f.bytes);pts=f.first;fragments.erase(it);
        }
        return decode(message,pts);
    }
    std::vector<ScteResult> decode(const Bytes& m,int64_t pts) {
        if(m.size()<4||m.size()>2000||get16(m,2)!=m.size())throw std::runtime_error("SCTE-104 message_size mismatch");
        uint16_t op=get16(m,0);
        if(op!=0xffff){
            // Link-management SOM messages carry no splice command.
            if((op==1||op==3||op==0x11)&&m.size()>=13)return {};
            throw std::runtime_error("Unsupported SCTE-104 single operation");
        }
        if(m.size()<12||m[4]!=0||m[9]!=0)throw std::runtime_error("Unsupported SCTE protocol version/truncated MOM");
        if(m[10]!=0)throw std::runtime_error("SCTE-104 UTC/VITC/GPI timestamp needs an external clock mapping; time_type 0 only");
        size_t offset=12;unsigned count=m[11];
        if(!count)throw std::runtime_error("SCTE-104 message has no operations");
        Bytes command,descriptors,key;uint8_t command_type=0xff,insert_type=0;uint32_t event=0;uint64_t target=0;
        struct Pending { ScteResult result; Bytes identity; uint8_t command_type; };
        std::vector<Pending> pending;
        auto finish = [&]() {
            if(command_type==0xff)return;
            // Supplemental descriptors belong only to the preceding normal request.
            key.insert(key.end(),descriptors.begin(),descriptors.end());
            key.push_back(m[5]);key.push_back(m[7]);key.push_back(m[8]);
            pending.push_back({{section35(command_type,command,descriptors),event,insert_type,target},key,command_type});
            command.clear();descriptors.clear();key.clear();
            command_type=0xff;insert_type=0;event=0;target=0;
        };
        for(unsigned i=0;i<count;++i){
            uint16_t id=get16(m,offset),len=get16(m,offset+2);offset+=4;
            if(offset+len>m.size())throw std::runtime_error("Truncated SCTE-104 operation payload");
            Bytes b(m.begin()+offset,m.begin()+offset+len);offset+=len;
            if(id==0x0108){
                if(command_type==0xff)throw std::runtime_error("SCTE descriptor request has no preceding command");
                if(b.empty())throw std::runtime_error("Missing SCTE descriptor count");
                size_t j=1;
                for(unsigned k=0;k<b[0];++k){if(j+2>b.size()||j+2+b[j+1]>b.size())throw std::runtime_error("Invalid SCTE descriptor length");size_t end=j+2+b[j+1];descriptors.insert(descriptors.end(),b.begin()+j,b.begin()+end);j=end;}
                if(j!=b.size())throw std::runtime_error("Trailing SCTE descriptor bytes");
                continue;
            }
            finish();
            key.push_back(id>>8);key.push_back(id);key.insert(key.end(),b.begin(),b.end());
            if(id==0x0101){
                if(len!=14)throw std::runtime_error("splice_request_data must contain 14 bytes");
                insert_type=b[0];if(insert_type<1||insert_type>5||b[13]>1)throw std::runtime_error("Invalid splice_insert_type/auto_return");
                event=(uint32_t(b[1])<<24)|(uint32_t(b[2])<<16)|(b[3]<<8)|b[4];
                bool cancel=insert_type==5,out=insert_type<=2,immediate=insert_type==2||insert_type==4;
                put32(command,event);command.push_back(cancel?0xff:0x7f);
                if(!cancel){
                    uint16_t duration=get16(b,9);bool has_duration=out&&duration;
                    command.push_back((out?0x80:0)|0x40|(has_duration?0x20:0)|(immediate?0x10:0)|0xf);
                    target=(uint64_t(pts)+uint64_t(get16(b,7))*90)&pts_mask;
                    if(!immediate)time33(command,target,0xfe);
                    if(has_duration)time33(command,uint64_t(duration)*9000,b[13]?0xfe:0x7e);
                    command.insert(command.end(),b.begin()+5,b.begin()+7);command.push_back(b[11]);command.push_back(b[12]);
                }
                command_type=5;
            }else if(id==0x0102){if(len)throw std::runtime_error("Invalid splice_null payload");command_type=0;}
            else if(id==0x0104){if(len!=2)throw std::runtime_error("Invalid time_signal payload");target=(uint64_t(pts)+uint64_t(get16(b,0))*90)&pts_mask;time33(command,target,0xfe);command_type=6;}
            else throw std::runtime_error("Unsupported SCTE-104 operation "+std::to_string(id));
        }
        if(offset!=m.size()||command_type==0xff)throw std::runtime_error("SCTE-104 trailing bytes or missing command");
        finish();
        // Validate the entire MOM before emitting any section or committing dedupe.
        for(auto i=seen.begin();i!=seen.end();)if(pts-i->second>450000||pts<i->second)i=seen.erase(i);else ++i;
        std::map<Bytes,int64_t> additions;
        std::vector<ScteResult> results;
        for(auto& item:pending){
            if(item.command_type!=0){
                if(seen.count(item.identity)||additions.count(item.identity))continue;
                if(seen.size()+additions.size()>=4096)throw std::runtime_error("SCTE duplicate cache full");
                additions[item.identity]=pts;
            }
            results.push_back(std::move(item.result));
        }
        seen.insert(additions.begin(),additions.end());
        return results;
    }
};
}
