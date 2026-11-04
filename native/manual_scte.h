/* Private 64-byte output journal records. Each muxer owns its read cursor. */
#ifndef SPANKVANC_MANUAL_SCTE_H
#define SPANKVANC_MANUAL_SCTE_H
#include <stdio.h>
#include <errno.h>
#ifdef __cplusplus
extern "C" {
#endif
#include "libavutil/file_open.h"
#include "libavutil/error.h"
#ifdef __cplusplus
}
#endif
static int spank_manual_open(FILE **file, const char *path)
{
    if (!path) return 0;
    *file = avpriv_fopen_utf8(path, "rb");
    if (!*file) return AVERROR(errno);
    setvbuf(*file, NULL, _IONBF, 0);
    return 0;
}
static int spank_manual_read(FILE *file, unsigned char *section)
{
    unsigned char record[64];
    long pos;
    size_t n;
    if (!file) return 0;
    pos = ftell(file);
    if (pos < 0) return AVERROR(EIO);
    clearerr(file);
    n = fread(record, 1, sizeof(record), file);
    if (n != sizeof(record)) {
        int error = ferror(file);
        if (fseek(file, pos, SEEK_SET)) return AVERROR(EIO);
        return error ? AVERROR(EIO) : 0;
    }
    if (record[0] < 20 || record[0] > 63 || record[1] != 0xfc)
        return AVERROR_INVALIDDATA;
    for (unsigned i = 0; i < record[0]; ++i) section[i] = record[i+1];
    return record[0];
}
#endif
