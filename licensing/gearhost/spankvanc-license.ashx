<%@ WebHandler Language="C#" Class="SpankVancLicenseHandler" %>
using System;
using System.Collections.Generic;
using System.Configuration;
using System.Data;
using System.Data.SqlClient;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web;
using System.Web.Script.Serialization;

public sealed class SpankVancLicenseHandler : IHttpHandler {
    public bool IsReusable { get { return false; } }
    static string Hash(string value) {
        using (var hash = SHA256.Create()) {
            return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(value))).Replace("-", "").ToLowerInvariant();
        }
    }
    static void Reply(HttpContext c, int status, object data) {
        c.Response.StatusCode = status;
        c.Response.TrySkipIisCustomErrors = true;
        c.Response.ContentType = "application/json; charset=utf-8";
        c.Response.Headers["Cache-Control"] = "no-store";
        c.Response.Headers["X-Content-Type-Options"] = "nosniff";
        c.Response.Write(new JavaScriptSerializer().Serialize(data));
    }
    static object Denied(string reason) { return new { valid = false, reason = reason }; }
    public void ProcessRequest(HttpContext c) {
        // License keys are never accepted in URLs or cookies. No CORS is enabled.
        if (!c.Request.IsSecureConnection) { Reply(c, 426, Denied("https_required")); return; }
        if (c.Request.HttpMethod != "POST") { Reply(c, 405, Denied("post_required")); return; }
        if (c.Request.ContentLength <= 0 || c.Request.ContentLength > 4096) { Reply(c, 400, Denied("invalid")); return; }
        try {
            Dictionary<string, object> data;
            using (var reader = new StreamReader(c.Request.InputStream, Encoding.UTF8)) {
                var raw = reader.ReadToEnd();
                if (raw.Length > 4096) { Reply(c, 400, Denied("invalid")); return; }
                data = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(raw);
            }
            if (data == null || !data.ContainsKey("key") || !data.ContainsKey("installation") || !data.ContainsKey("action")) {
                Reply(c, 400, Denied("invalid")); return;
            }
            string key = data["key"] as string, installation = data["installation"] as string, action = data["action"] as string;
            if (key == null || installation == null || !Regex.IsMatch(key, @"\ASV1-[A-Za-z0-9_-]{43}\z") ||
                    !Regex.IsMatch(installation, @"\A[0-9a-f]{64}\z") || (action != "activate" && action != "check")) {
                Reply(c, 400, Denied("invalid")); return;
            }
            var setting = ConfigurationManager.ConnectionStrings["TvRewards"];
            if (setting == null) throw new InvalidOperationException();
            using (var db = new SqlConnection(setting.ConnectionString)) {
                db.Open();
                using (var tx = db.BeginTransaction(IsolationLevel.Serializable)) {
                    long now;
                    using (var clock = new SqlCommand("SELECT DATEDIFF(second,CONVERT(datetime,'19700101',112),GETUTCDATE())", db, tx)) {
                        clock.CommandTimeout = 5; now = Convert.ToInt64(clock.ExecuteScalar());
                    }
                    string bound = null; long? activated = null, expires = null; bool exists = false, revoked = false;
                    using (var cmd = new SqlCommand("SELECT installation_hash,activated_at,expires_at,revoked FROM dbo.spankvanc_licenses WITH (UPDLOCK,HOLDLOCK) WHERE key_hash=@key", db, tx)) {
                        cmd.CommandTimeout = 5;
                        cmd.Parameters.Add("@key", SqlDbType.Char, 64).Value = Hash(key);
                        using (var row = cmd.ExecuteReader()) {
                            if (row.Read()) {
                                exists = true; bound = row.IsDBNull(0) ? null : row.GetString(0);
                                activated = row.IsDBNull(1) ? (long?)null : row.GetInt64(1);
                                expires = row.IsDBNull(2) ? (long?)null : row.GetInt64(2);
                                revoked = row.GetBoolean(3);
                            }
                        }
                    }
                    string reason = !exists || revoked ? "invalid" : bound != null && bound != Hash(installation) ? "bound" :
                        expires.HasValue && expires.Value <= now ? "expired" : !activated.HasValue && action != "activate" ? "inactive" : null;
                    if (reason != null) { tx.Rollback(); Reply(c, 403, Denied(reason)); return; }
                    // First activation is atomic. Repeated requests never extend the window.
                    if (!activated.HasValue) { activated = now; expires = now + 2592000L; bound = Hash(installation); }
                    using (var cmd = new SqlCommand("UPDATE dbo.spankvanc_licenses SET installation_hash=@installation,activated_at=@activated,expires_at=@expires,last_seen=@now WHERE key_hash=@key", db, tx)) {
                        cmd.CommandTimeout = 5;
                        cmd.Parameters.Add("@key", SqlDbType.Char, 64).Value = Hash(key);
                        cmd.Parameters.Add("@installation", SqlDbType.Char, 64).Value = bound;
                        cmd.Parameters.Add("@activated", SqlDbType.BigInt).Value = activated.Value;
                        cmd.Parameters.Add("@expires", SqlDbType.BigInt).Value = expires.Value;
                        cmd.Parameters.Add("@now", SqlDbType.BigInt).Value = now;
                        cmd.ExecuteNonQuery();
                    }
                    tx.Commit();
                    Reply(c, 200, new { valid = true, server_time = now, activated_at = activated.Value, expires_at = expires.Value });
                }
            }
        } catch (ArgumentException) { Reply(c, 400, Denied("invalid")); }
          catch (Exception) { Reply(c, 503, Denied("unavailable")); }
    }
}
