// Linux DeckLink SDK ANC diagnostic. No SDK files are redistributed here.
// Copies packet payloads during the callback; writes NDJSON outside that thread.
#include "DeckLinkAPI.h"
#include "anc_policy.hpp"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>

template<class T> struct Com {
    T* p = nullptr;
    ~Com() { if (p) p->Release(); }
    T* operator->() const { return p; }
    void** out() { return reinterpret_cast<void**>(&p); }
};
static volatile std::sig_atomic_t stopping = 0;
static void interrupted(int) { stopping = 1; }
static void check(HRESULT result, const char* action) {
    if (result != S_OK) throw std::runtime_error(action);
}
static std::string quote(const char* text) {
    std::ostringstream out;
    out << '"';
    for (const unsigned char c : std::string(text ? text : "")) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c);
        else out << c;
    }
    out << '"';
    return out.str();
}
static std::string mode_code(BMDDisplayMode mode) {
    std::string text;
    for (int shift = 24; shift >= 0; shift -= 8) text += char((uint32_t(mode) >> shift) & 255);
    return text;
}
static BMDDisplayMode parse_mode(const std::string& text) {
    if (text.size() != 4) throw std::runtime_error("Mode must be the four-character code from --list");
    uint32_t value = 0;
    for (unsigned char c : text) value = (value << 8) | c;
    return static_cast<BMDDisplayMode>(value);
}
struct Frame {
    int64_t pts = 0, duration = 0;
    bool signal = false;
    std::vector<spankvanc::AncPacket> packets;
};

class Capture final : public IDeckLinkInputCallback {
    std::atomic<ULONG> references{1};
public:
    std::mutex mutex;
    std::condition_variable changed;
    std::deque<Frame> frames;
    std::string failure;
    HRESULT QueryInterface(REFIID iid, LPVOID* result) override {
        if (!result) return E_POINTER;
        const REFIID unknown = IID_IUnknown;
        if (!memcmp(&iid, &IID_IDeckLinkInputCallback, sizeof(iid)) || !memcmp(&iid, &unknown, sizeof(iid))) {
            *result = static_cast<IDeckLinkInputCallback*>(this); AddRef(); return S_OK;
        }
        *result = nullptr;
        return E_NOINTERFACE;
    }
    ULONG AddRef() override { return ++references; }
    ULONG Release() override { ULONG count = --references; if (!count) delete this; return count; }
    HRESULT VideoInputFormatChanged(BMDVideoInputFormatChangedEvents, IDeckLinkDisplayMode*, BMDDetectedVideoInputFormatFlags) override {
        fail("Input format changed; stop and choose the new mode");
        return S_OK;
    }
    void fail(const std::string& message) {
        std::lock_guard<std::mutex> lock(mutex);
        if (failure.empty()) failure = message;
        changed.notify_one();
    }
    HRESULT VideoInputFrameArrived(IDeckLinkVideoInputFrame* video, IDeckLinkAudioInputPacket*) override {
        if (!video) return S_OK;
        try {
            Frame frame;
            check(video->GetStreamTime(&frame.pts, &frame.duration, 90000), "No frame stream timestamp");
            frame.signal = !(video->GetFlags() & bmdFrameHasNoInputSource);
            if (frame.signal) {
                Com<IDeckLinkVideoFrameAncillaryPackets> packets;
                check(video->QueryInterface(IID_IDeckLinkVideoFrameAncillaryPackets, packets.out()), "ANC packet interface unavailable for this card/mode");
                Com<IDeckLinkAncillaryPacketIterator> iterator;
                check(packets->GetPacketIterator(&iterator.p), "Cannot enumerate ANC packets");
                for (;;) {
                    Com<IDeckLinkAncillaryPacket> packet;
                    if (iterator->Next(&packet.p) != S_OK) break;
                    const void* bytes = nullptr;
                    uint32_t length = 0;
                    check(packet->GetBytes(bmdAncillaryPacketFormatUInt8, &bytes, &length), "Cannot read ANC bytes");
                    if ((length && !bytes) || length > 255 || frame.packets.size() >= 128)
                        throw std::runtime_error("ANC packet/frame limit exceeded");
                    spankvanc::AncPacket copy{packet->GetDID(), packet->GetSDID(), packet->GetLineNumber(),
                                            packet->GetDataStreamIndex(), frame.pts, {}};
                    if (length) {
                        const auto* data = static_cast<const uint8_t*>(bytes);
                        copy.payload.assign(data, data + length);
                    }
                    frame.packets.push_back(std::move(copy));
                }
            }
            std::lock_guard<std::mutex> lock(mutex);
            if (frames.size() >= 256) {
                if (failure.empty()) failure = "ANC diagnostic queue overflow; capture stopped without silent packet loss";
            } else frames.push_back(std::move(frame));
            changed.notify_one();
        } catch (const std::exception& e) { fail(e.what()); }
        return S_OK;
    }
};

static void list_device(IDeckLink* device, int index) {
    const char* name = nullptr;
    check(device->GetDisplayName(&name), "Cannot read device name");
    std::string display = quote(name);
    free(const_cast<char*>(name));
    Com<IDeckLinkInput> input;
    Com<IDeckLinkOutput> output;
    bool capture = device->QueryInterface(IID_IDeckLinkInput, input.out()) == S_OK;
    bool playback = device->QueryInterface(IID_IDeckLinkOutput, output.out()) == S_OK;
    Com<IDeckLinkProfileAttributes> attributes;
    int64_t duplex_mode = 0;
    const char* duplex = "unknown";
    if (device->QueryInterface(IID_IDeckLinkProfileAttributes, attributes.out()) == S_OK &&
        attributes->GetInt(BMDDeckLinkDuplex, &duplex_mode) == S_OK) {
        if (duplex_mode == bmdDuplexFull) duplex = "full";
        else if (duplex_mode == bmdDuplexHalf) duplex = "half";
        else if (duplex_mode == bmdDuplexSimplex) duplex = "simplex";
        else if (duplex_mode == bmdDuplexInactive) duplex = "inactive";
    }
    std::cout << "{\"device\":" << index << ",\"name\":" << display
              << ",\"input\":" << (capture ? "true" : "false")
              << ",\"duplex\":" << quote(duplex)
              << ",\"output\":" << (playback ? "true" : "false") << ",\"modes\":[";
    Com<IDeckLinkDisplayModeIterator> modes;
    bool comma = false;
    if (capture && input->GetDisplayModeIterator(&modes.p) == S_OK) {
        for (;;) {
            Com<IDeckLinkDisplayMode> mode;
            if (modes->Next(&mode.p) != S_OK) break;
            const char* mode_name = nullptr;
            if (mode->GetName(&mode_name) != S_OK) continue;
            BMDTimeValue duration;
            BMDTimeScale scale;
            mode->GetFrameRate(&duration, &scale);
            if (comma) std::cout << ',';
            comma = true;
            std::cout << "{\"code\":" << quote(mode_code(mode->GetDisplayMode()).c_str())
                      << ",\"name\":" << quote(mode_name) << ",\"duration\":" << duration << ",\"timescale\":" << scale << '}';
            free(const_cast<char*>(mode_name));
        }
    }
    std::cout << "]}\n";
}

static void print_frame(const Frame& frame) {
    std::cout << "{\"pts90k\":" << frame.pts << ",\"duration90k\":" << frame.duration
              << ",\"signal\":" << (frame.signal ? "true" : "false") << ",\"packets\":[";
    bool comma = false;
    for (const auto& packet : frame.packets) {
        if (comma) std::cout << ',';
        comma = true;
        const auto type = spankvanc::classify(packet);
        const char* kind = type == spankvanc::AncKind::Captions ? "captions" : type == spankvanc::AncKind::Scte104 ? "scte104" : "other";
        std::cout << "{\"did\":" << int(packet.did) << ",\"sdid\":" << int(packet.sdid)
                  << ",\"line\":" << packet.line << ",\"stream\":" << int(packet.stream)
                  << ",\"kind\":\"" << kind << "\",\"payload_hex\":\"";
        for (uint8_t byte : packet.payload) std::cout << std::hex << std::setw(2) << std::setfill('0') << int(byte);
        std::cout << std::dec << "\"}";
    }
    std::cout << "]}\n";
}

int main(int argc, char** argv) {
    try {
        bool list = false;
        int selected = 0, seconds = 30;
        std::string mode_text;
        for (int i = 1; i < argc; ++i) {
            std::string option = argv[i];
            if (option == "--help") {
                std::cout << "SpankVANC DeckLink ANC diagnostic (Linux SDK)\n"
                          << "  --list\n  --device N --mode FOURCC [--seconds 30]\n"
                          << "Writes raw frame-associated ANC as NDJSON; does not decode SCTE or captions.\n";
                return 0;
            }
            if (option == "--list") list = true;
            else if (i + 1 < argc && option == "--device") selected = std::stoi(argv[++i]);
            else if (i + 1 < argc && option == "--mode") mode_text = argv[++i];
            else if (i + 1 < argc && option == "--seconds") seconds = std::stoi(argv[++i]);
            else throw std::runtime_error("Unknown option or missing value; see --help");
        }
        if (selected < 0 || seconds < 1 || seconds > 3600) throw std::runtime_error("Invalid device or capture duration");
        if (!list && mode_text.empty()) throw std::runtime_error("Use --list or choose --mode FOURCC");
        Com<IDeckLinkIterator> devices;
        devices.p = CreateDeckLinkIteratorInstance();
        if (!devices.p) throw std::runtime_error("DeckLink driver/API unavailable; install compatible Blackmagic Desktop Video");
        int index = 0;
        bool found = false;
        for (;;) {
            Com<IDeckLink> device;
            if (devices->Next(&device.p) != S_OK) break;
            if (list) { list_device(device.p, index++); found = true; continue; }
            if (index++ != selected) continue;
            found = true;
            Com<IDeckLinkInput> input;
            check(device->QueryInterface(IID_IDeckLinkInput, input.out()), "Selected device cannot capture");
            const auto mode = parse_mode(mode_text);
            bool supported = false;
            BMDDisplayMode actual;
            check(input->DoesSupportVideoMode(bmdVideoConnectionSDI, mode, bmdFormat10BitYUV,
                  bmdNoVideoInputConversion, bmdSupportedVideoModeDefault, &actual, &supported), "Cannot query video mode");
            if (!supported) throw std::runtime_error("Selected SDI mode does not support 10-bit YUV capture");
            Com<IDeckLinkConfiguration> settings;
            check(device->QueryInterface(IID_IDeckLinkConfiguration, settings.out()), "Cannot query SDI input connection");
            int64_t connection = 0;
            check(settings->GetInt(bmdDeckLinkConfigVideoInputConnection, &connection), "Cannot read input connection");
            if (connection != bmdVideoConnectionSDI)
                throw std::runtime_error("Select the SDI input in Blackmagic Desktop Video Setup first");
            Com<Capture> capture;
            capture.p = new Capture;
            check(input->SetCallback(capture.p), "Cannot register capture callback");
            auto result = input->EnableVideoInput(mode, bmdFormat10BitYUV, bmdVideoInputFlagDefault);
            if (result != S_OK) { input->SetCallback(nullptr); check(result, "Cannot enable input; device may be busy"); }
            result = input->StartStreams();
            if (result != S_OK) { input->DisableVideoInput(); input->SetCallback(nullptr); check(result, "Cannot start capture"); }
            std::signal(SIGINT, interrupted);
            std::signal(SIGTERM, interrupted);
            auto end = std::chrono::steady_clock::now() + std::chrono::seconds(seconds);
            std::string failure;
            uint64_t frame_count = 0, signal_count = 0, packet_count = 0;
            auto emit = [&](const Frame& frame) {
                print_frame(frame);
                ++frame_count;
                if (frame.signal) ++signal_count;
                packet_count += frame.packets.size();
            };
            while (!stopping && std::chrono::steady_clock::now() < end) {
                Frame frame;
                bool have = false;
                {
                    std::unique_lock<std::mutex> lock(capture->mutex);
                    capture->changed.wait_for(lock, std::chrono::milliseconds(100), [&] { return !capture->frames.empty() || !capture->failure.empty(); });
                    if (!capture->failure.empty()) { failure = capture->failure; break; }
                    if (!capture->frames.empty()) { frame = std::move(capture->frames.front()); capture->frames.pop_front(); have = true; }
                }
                if (have) emit(frame);
            }
            input->StopStreams(); input->DisableVideoInput(); input->SetCallback(nullptr);
            {
                std::lock_guard<std::mutex> lock(capture->mutex);
                if (!capture->failure.empty()) failure = capture->failure;
                for (const auto& frame : capture->frames) emit(frame);
            }
            std::cerr << "Captured " << frame_count << " frames, " << signal_count
                      << " with signal, " << packet_count << " ANC packets\n";
            if (!failure.empty()) throw std::runtime_error(failure);
            if (!frame_count) throw std::runtime_error("No video frames received; check source mode and connection");
            if (!signal_count) throw std::runtime_error("No valid input signal received");
            break;
        }
        if (!found) throw std::runtime_error("No matching DeckLink device found");
    } catch (const std::exception& e) {
        std::cerr << "SpankVANC: " << e.what() << '\n'; return 1;
    }
    return 0;
}
