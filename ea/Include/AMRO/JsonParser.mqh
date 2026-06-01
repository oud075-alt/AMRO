//+------------------------------------------------------------------+
//| AMRO — JsonParser.mqh                                            |
//| Role: JSON serialization / deserialization (lightweight)         |
//| Constitutional Rule: transmit data faithfully — no interpretation|
//+------------------------------------------------------------------+
#ifndef AMRO_JSON_PARSER_MQH
#define AMRO_JSON_PARSER_MQH

//+------------------------------------------------------------------+
//| Extract string value from flat JSON key                          |
//| e.g.  {"key":"value"} → returns "value"                         |
//+------------------------------------------------------------------+
string JsonGetString(const string &json, const string key)
{
    string pattern = "\"" + key + "\"";
    int pos = StringFind(json, pattern);
    if (pos < 0) return "";

    int colon = StringFind(json, ":", pos + StringLen(pattern));
    if (colon < 0) return "";

    int start = colon + 1;
    while (start < StringLen(json) && StringGetCharacter(json, start) == ' ')
        start++;

    if (StringGetCharacter(json, start) == '"')
    {
        start++;
        int end = StringFind(json, "\"", start);
        if (end < 0) return "";
        return StringSubstr(json, start, end - start);
    }
    return "";
}

//+------------------------------------------------------------------+
//| Extract numeric (double) value from flat JSON key                |
//+------------------------------------------------------------------+
double JsonGetDouble(const string &json, const string key)
{
    string pattern = "\"" + key + "\"";
    int pos = StringFind(json, pattern);
    if (pos < 0) return 0.0;

    int colon = StringFind(json, ":", pos + StringLen(pattern));
    if (colon < 0) return 0.0;

    int start = colon + 1;
    while (start < StringLen(json) && StringGetCharacter(json, start) == ' ')
        start++;

    int end = start;
    int len = StringLen(json);
    while (end < len)
    {
        ushort c = StringGetCharacter(json, end);
        if (c == ',' || c == '}' || c == '\n' || c == '\r')
            break;
        end++;
    }
    return StringToDouble(StringSubstr(json, start, end - start));
}

//+------------------------------------------------------------------+
//| Extract boolean value from flat JSON key                         |
//+------------------------------------------------------------------+
bool JsonGetBool(const string &json, const string key)
{
    string pattern = "\"" + key + "\"";
    int pos = StringFind(json, pattern);
    if (pos < 0) return false;

    int colon = StringFind(json, ":", pos + StringLen(pattern));
    if (colon < 0) return false;

    int start = colon + 1;
    while (start < StringLen(json) && StringGetCharacter(json, start) == ' ')
        start++;

    return (StringSubstr(json, start, 4) == "true");
}

//+------------------------------------------------------------------+
//| Build minimal JSON payload for telemetry                         |
//+------------------------------------------------------------------+
string JsonBuildTelemetry(
    const string symbol,
    const string event_type,
    const string detail,
    const double price,
    const long   ticket
)
{
    return StringFormat(
        "{\"symbol\":\"%s\",\"event\":\"%s\",\"detail\":\"%s\","
        "\"price\":%.5f,\"ticket\":%I64d,\"ts\":%I64d}",
        symbol, event_type, detail, price, ticket,
        (long)TimeCurrent()
    );
}

//+------------------------------------------------------------------+
//| Build heartbeat JSON payload                                     |
//+------------------------------------------------------------------+
string JsonBuildHeartbeat(
    const string symbol,
    const string status,
    const int    open_positions,
    const double equity,
    const double balance
)
{
    return StringFormat(
        "{\"symbol\":\"%s\",\"status\":\"%s\","
        "\"open_positions\":%d,\"equity\":%.2f,\"balance\":%.2f,"
        "\"ts\":%I64d}",
        symbol, status, open_positions, equity, balance,
        (long)TimeCurrent()
    );
}

//+------------------------------------------------------------------+
//| Build trade report JSON payload                                  |
//+------------------------------------------------------------------+
string JsonBuildReport(
    const string symbol,
    const string action,
    const long   ticket,
    const double lot,
    const double entry,
    const double sl,
    const double tp,
    const string reason
)
{
    // sanitize reason — remove special chars that break JSON
    string r = reason;
    StringReplace(r, "\"", "'");
    StringReplace(r, "\\", "/");
    StringReplace(r, "\n", " ");
    StringReplace(r, "\r", " ");
    StringReplace(r, "—", "-");
    StringReplace(r, "–", "-");
    if (StringLen(r) > 100) r = StringSubstr(r, 0, 100);

    return StringFormat(
        "{\"symbol\":\"%s\",\"action\":\"%s\",\"ticket\":%I64d,"
        "\"lot\":%.2f,\"entry\":%.5f,\"sl\":%.5f,\"tp\":%.5f,"
        "\"reason\":\"%s\",\"ts\":%I64d}",
        symbol, action, ticket, lot, entry, sl, tp, r,
        (long)TimeCurrent()
    );
}

#endif // AMRO_JSON_PARSER_MQH
