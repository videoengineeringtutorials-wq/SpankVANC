/* Service announcement for generated captions only; source pass stays opaque. */
#ifndef SPANKVANC_CAPTION_SERVICES_H
#define SPANKVANC_CAPTION_SERVICES_H
#include <string.h>
#include <libklvanc/vanc.h>
static inline void spank_caption_services(struct klvanc_packet_eia_708b_s *cdp,
                                          int format, const char *language)
{
    unsigned n=0;
    if (!format) return;
    cdp->header.svcinfo_present=1;
    cdp->header.svc_info_start=cdp->header.svc_info_complete=1;
    cdp->ccsvc.svc_info_start=cdp->ccsvc.svc_info_complete=1;
    for (int digital=0;digital<=1;digital++) {
        struct klvanc_packet_eia_708b_ccsvcinfo_entry *entry;
        if (!(format & (digital ? 2 : 1))) continue;
        entry=&cdp->ccsvc.svc[n++];
        entry->caption_service_number=digital ? 1 : 0;
        memcpy(entry->svc_data_byte,language && strlen(language)==3 ? language : "und",3);
        entry->svc_data_byte[3]=digital ? 0xc1 : 0x7e;
        entry->svc_data_byte[4]=0x7f; /* wide aspect, not easy-reader, reserved */
        entry->svc_data_byte[5]=0xff;
    }
    cdp->ccsvc.svc_count=n;
}
#endif
