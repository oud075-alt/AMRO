//+------------------------------------------------------------------+
//| AMRO — ApiClient.mqh                                             |
//| Role: HTTP communication layer via MQL5 WebRequest              |
//| Constitutional Rule: transmit faithfully — never modify payload  |
//| Note: add server URL to MT5 Tools → Options → Expert Advisors   |
//+------------------------------------------------------------------+
#ifndef AMRO_API_CLIENT_MQH
#define AMRO_API_CLIENT_MQH

#include "ConfigManager.mqh"

//+------------------------------------------------------------------+
//| Result container for HTTP calls                                  |
//+------------------------------------------------------------------+
struct ApiResponse
{
    int    http_code;   // 200 / 422 / 500 / -1 (network error)
    string body;        // raw response body
    bool   ok;          // true if http_code == 200
};

//+------------------------------------------------------------------+
//| Internal: build full URL                                         |
//+------------------------------------------------------------------+
string _ApiUrl(const AMROConfig &cfg, const string path)
{
    string base = cfg.api_base_url;
    // strip trailing slash
    if (StringLen(base) > 0 && StringGetCharacter(base, StringLen(base)-1) == '/')
        base = StringSubstr(base, 0, StringLen(base)-1);
    return base + path;
}

//+------------------------------------------------------------------+
//| Internal: build auth headers array                               |
//+------------------------------------------------------------------+
void _ApiHeaders(const AMROConfig &cfg, string &headers)
{
    headers = "Content-Type: application/json\r\n";
    if (StringLen(cfg.api_key) > 0)
        headers += "X-API-Key: " + cfg.api_key + "\r\n";
}

//+------------------------------------------------------------------+
//| GET request                                                      |
//+------------------------------------------------------------------+
ApiResponse ApiGet(const AMROConfig &cfg, const string path)
{
    ApiResponse res;
    res.http_code = -1;
    res.ok = false;
    res.body = "";

    string url = _ApiUrl(cfg, path);
    string headers = "";
    _ApiHeaders(cfg, headers);

    char   result_body[];
    string result_headers;

    int attempts = 0;
    while (attempts < cfg.max_retries)
    {
        char dummy[];   // empty POST body for GET
        res.http_code = WebRequest(
            "GET", url, headers, cfg.request_timeout_ms,
            dummy, result_body, result_headers
        );

        if (res.http_code == 200) break;

        attempts++;
        if (attempts < cfg.max_retries)
            Sleep(500 * attempts);   // back-off
    }

    res.body = CharArrayToString(result_body, 0, WHOLE_ARRAY, CP_UTF8);
    res.ok   = (res.http_code == 200);

    if (!res.ok)
        PrintFormat("[ApiClient] GET %s → code=%d", path, res.http_code);

    return res;
}

//+------------------------------------------------------------------+
//| POST request                                                     |
//+------------------------------------------------------------------+
ApiResponse ApiPost(const AMROConfig &cfg, const string path, const string json_body)
{
    ApiResponse res;
    res.http_code = -1;
    res.ok = false;
    res.body = "";

    string url = _ApiUrl(cfg, path);
    string headers = "";
    _ApiHeaders(cfg, headers);

    char   send_data[];
    char   result_body[];
    string result_headers;

    StringToCharArray(json_body, send_data, 0, StringLen(json_body), CP_UTF8);
    // remove null terminator that StringToCharArray appends
    ArrayResize(send_data, StringLen(json_body));

    int attempts = 0;
    while (attempts < cfg.max_retries)
    {
        res.http_code = WebRequest(
            "POST", url, headers, cfg.request_timeout_ms,
            send_data, result_body, result_headers
        );

        if (res.http_code == 200 || res.http_code == 201) break;

        attempts++;
        if (attempts < cfg.max_retries)
            Sleep(500 * attempts);
    }

    res.body = CharArrayToString(result_body, 0, WHOLE_ARRAY, CP_UTF8);
    res.ok   = (res.http_code == 200 || res.http_code == 201);

    if (!res.ok)
        PrintFormat("[ApiClient] POST %s → code=%d body=%s",
                    path, res.http_code, StringSubstr(res.body, 0, 200));

    return res;
}

//+------------------------------------------------------------------+
//| Convenience: poll decision endpoint                              |
//| GET /api/ea/decision?symbol=SYMBOL                              |
//+------------------------------------------------------------------+
ApiResponse ApiGetDecision(const AMROConfig &cfg, const string symbol)
{
    return ApiGet(cfg, "/api/ea/decision?symbol=" + symbol);
}

//+------------------------------------------------------------------+
//| Convenience: POST telemetry                                      |
//+------------------------------------------------------------------+
ApiResponse ApiPostTelemetry(const AMROConfig &cfg, const string json_body)
{
    return ApiPost(cfg, "/api/ea/telemetry", json_body);
}

//+------------------------------------------------------------------+
//| Convenience: POST heartbeat                                      |
//+------------------------------------------------------------------+
ApiResponse ApiPostHeartbeat(const AMROConfig &cfg, const string json_body)
{
    return ApiPost(cfg, "/api/ea/heartbeat", json_body);
}

//+------------------------------------------------------------------+
//| Convenience: POST trade report                                   |
//+------------------------------------------------------------------+
ApiResponse ApiPostReport(const AMROConfig &cfg, const string json_body)
{
    return ApiPost(cfg, "/api/ea/report", json_body);
}

#endif // AMRO_API_CLIENT_MQH
