/* SpankVANC generated-text CEA-708 Service 1 encoder.
 * Input is our paced, parity-protected CC1 journal, not arbitrary source 608.
 * Commands select a visible, bottom-centred, two-row roll-up window. */
#ifndef SPANKVANC_CEA708_ENCODER_H
#define SPANKVANC_CEA708_ENCODER_H
#include <stdint.h>
#include <string.h>

typedef struct Spank708 {
    unsigned sequence;
    int initialized;
    int channel;
    uint8_t previous_a, previous_b;
} Spank708;

/* Return complete 708 commands for one generated CC1 pair (<=15 bytes). */
static inline unsigned spank708_pair(Spank708 *s, uint8_t a, uint8_t b, uint8_t *out)
{
    unsigned n = 0;
    a &= 0x7f; b &= 0x7f;
    /* CC1 and CC2 share field 1. Track channel controls before converting
     * printable pairs, so Spanish CC2 never appears in English Service 1. */
    if (a >= 0x10 && a <= 0x1f) s->channel = (a & 8) != 0;
    if (s->channel) {
        s->previous_a = s->previous_b = 0;
        return 0;
    }
    if (a == 0x14 && b >= 0x20 && b <= 0x7f) {
        /* 608 controls are sent twice. Suppress exactly the second copy. */
        if (s->previous_a == a && s->previous_b == b) {
            s->previous_a = s->previous_b = 0;
            return 0;
        }
        s->previous_a = a; s->previous_b = b;
        if (b == 0x25) {
            const uint8_t window[] = {0x98,0x38,0xdf,0x32,0x71,0x1f,0x21,
                                      0x80,0x92,0x01,0x00};
            if (!s->initialized) {out[n++] = 0x8f; s->initialized = 1;}
            memcpy(out+n, window, sizeof(window)); n += sizeof(window);
        } else if (s->initialized && b == 0x2d) {
            out[n++] = 0x0d; /* CR scrolls the two-row window. */
        } else if (s->initialized && b == 0x2c) {
            const uint8_t clear[] = {0x80,0x88,0x01,0x92,0x01,0x00};
            memcpy(out+n, clear, sizeof(clear)); n += sizeof(clear);
        }
        /* PAC and delete-to-end-of-row are redundant after 708 CR/SPL. */
        return n;
    }
    s->previous_a = s->previous_b = 0;
    if (!s->initialized) return 0;
    if (a >= 0x20 && a <= 0x7e) out[n++] = a;
    if (b >= 0x20 && b <= 0x7e) out[n++] = b;
    return n;
}

/* One complete Service 1 block per packet; no commands cross block boundaries.
 * Start tuple is cc_type=3, continuation tuples cc_type=2. */
static inline unsigned spank708_packet(Spank708 *s, const uint8_t *commands,
                                      unsigned count, uint8_t *triplets)
{
    uint8_t packet[34];
    unsigned total, tuples;
    if (!count || count > 31) return 0;
    total = (count + 3) & ~1U; /* header + service header + commands, even */
    packet[0] = ((s->sequence++ & 3) << 6) | (total / 2);
    packet[1] = 0x20 | count;
    memcpy(packet+2, commands, count);
    if (total > count+2) packet[total-1] = 0; /* null service block padding */
    tuples = total / 2;
    for (unsigned i=0; i<tuples; ++i) {
        triplets[i*3] = i ? 0xfe : 0xff;
        triplets[i*3+1] = packet[i*2]; triplets[i*3+2] = packet[i*2+1];
    }
    return tuples;
}
#endif
