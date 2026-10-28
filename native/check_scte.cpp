#include "scte104.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
int main(int argc,char**argv){
 try{
 if(argc!=3 && argc!=4)throw std::runtime_error("Usage: check-scte ST2010_HEX PTS90K [continue|strict]");
 std::istringstream input(argv[1]);std::string hex;spankvanc::Scte104Decoder d;int64_t pts=std::stoll(argv[2]);
 const bool recovery=argc==4,strict=recovery && std::string(argv[3])=="strict";
 while(std::getline(input,hex,',')) {
 if(hex.size()%2)throw std::runtime_error("Odd hex length");
 spankvanc::Bytes b;for(size_t i=0;i<hex.size();i+=2)b.push_back(std::stoul(hex.substr(i,2),nullptr,16));
 auto results=recovery?d.consume(b.data(),b.size(),pts,0,strict):d.feed(b.data(),b.size(),pts);
 for(auto&r:results){for(auto v:r.section)std::cout<<std::hex<<std::setfill('0')<<std::setw(2)<<int(v);std::cout<<'\n';}
 pts+=3003;
 }
 if(recovery){std::cerr<<"rejected="<<d.rejected<<" failed="<<d.failed.load()<<" reason="<<d.last_error<<'\n';if(d.failed.load())return 2;}
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}return 0;
}
