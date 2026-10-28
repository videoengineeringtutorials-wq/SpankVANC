#include "scte35_to104.hpp"
#include <iostream>
#include <iomanip>
int main(int argc,char**argv) {
 try {
  if(argc<3)throw std::runtime_error("Usage: check-scte-output SECTION35_HEX FRAME_PTS90K [late-repeat]");
  std::string hex=argv[1];if(hex.size()%2)throw std::runtime_error("Odd hex");
  spankvanc::Bytes section;
  for(size_t i=0;i<hex.size();i+=2)section.push_back(std::stoul(hex.substr(i,2),nullptr,16));
  spankvanc::Scte35To104 converter;int64_t pts=std::stoll(argv[2]);auto message=converter.convert(section,pts);
  auto packets=spankvanc::fragment104(message);auto blob=spankvanc::pack104(packets);
  auto unpacked=spankvanc::unpack104(blob.data(),blob.size());
  if(argc>3 && !converter.convert(section,pts+45000).empty())throw std::runtime_error("Repeated cue was not suppressed");
  for(const auto& packet:unpacked){for(uint8_t v:packet.payload)std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<int(v);std::cout<<'\n';}
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
