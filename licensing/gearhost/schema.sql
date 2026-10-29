-- Additive, isolated table. No changes to existing TV-Watermark tables.
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF OBJECT_ID('dbo.spankvanc_licenses', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.spankvanc_licenses (
        key_hash char(64) NOT NULL PRIMARY KEY,
        label nvarchar(128) NOT NULL,
        issued_at bigint NOT NULL,
        installation_hash char(64) NULL,
        activated_at bigint NULL,
        expires_at bigint NULL,
        last_seen bigint NULL,
        revoked bit NOT NULL DEFAULT 0,
        CONSTRAINT spankvanc_license_window CHECK (
            (activated_at IS NULL AND expires_at IS NULL AND installation_hash IS NULL)
            OR (activated_at IS NOT NULL AND installation_hash IS NOT NULL
                AND expires_at IS NOT NULL AND expires_at=activated_at+2592000))
    );
END;
IF COL_LENGTH('dbo.spankvanc_licenses', 'shared') IS NULL
    ALTER TABLE dbo.spankvanc_licenses ADD shared bit NOT NULL
        CONSTRAINT spankvanc_shared_default DEFAULT 0 WITH VALUES;
IF OBJECT_ID('dbo.spankvanc_license_activations', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.spankvanc_license_activations (
        key_hash char(64) NOT NULL,
        installation_hash char(64) NOT NULL,
        activated_at bigint NOT NULL,
        expires_at bigint NOT NULL,
        last_seen bigint NOT NULL,
        CONSTRAINT spankvanc_activation_pk PRIMARY KEY (key_hash, installation_hash),
        CONSTRAINT spankvanc_activation_key FOREIGN KEY (key_hash)
            REFERENCES dbo.spankvanc_licenses(key_hash),
        CONSTRAINT spankvanc_activation_window CHECK (expires_at=activated_at+2592000)
    );
END;
COMMIT;
