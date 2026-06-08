#!/bin/sh
set -eu

file="$1"
awk '
    index($0, "if ($cookie_womginx_are_you_a_bot != '\''no'\'') {") {
        skip = 1
        depth = 1
        next
    }
    skip {
        depth += gsub(/\{/, "{")
        depth -= gsub(/\}/, "}")
        if (depth <= 0) skip = 0
        next
    }
    { print }
' "$file" > "$file.tmp"

mv "$file.tmp" "$file"

sed -i 's|$relativescheme://$host|$relativescheme://$http_host|g' "$file"
sed -i 's|resolver 1.1.1.1;|resolver 1.1.1.1 ipv6=off;|' "$file"
sed -i 's|resolver 1.1.1.3;|resolver 1.1.1.3 ipv6=off;|' "$file"

sed -i "/sub_filter 'src=\\\"\\/\\//a\\                sub_filter 'href=\\\"//' '\$processed_flag_attribute href=\\\"/main/\$relativescheme://';" "$file"
sed -i "/sub_filter 'src=\\\"\\/'/a\\                sub_filter 'href=\\\"/' '\$processed_flag_attribute href=\\\"/main/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'src=\\\"https:\\/\\//a\\                sub_filter 'href=\\\"https://' '\$processed_flag_attribute href=\\\"/main/https://';" "$file"
sed -i "/sub_filter 'src=\\\"http:\\/\\//a\\                sub_filter 'href=\\\"http://' '\$processed_flag_attribute href=\\\"/main/http://';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'import \\\"/' 'import \\\"/main/js_/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'from \\\"/' 'from \\\"/main/js_/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'import(\\\"/' 'import(\\\"/main/js_/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'import( \\\"/' 'import( \\\"/main/js_/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'fetch(\\\"/' 'fetch(\\\"/main/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter 'fetch( \\\"/' 'fetch( \\\"/main/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'href=\\\"\\/'/a\\                sub_filter '\\\"/cdn/' '\\\"/main/\$dest_hostwithscheme/cdn/';" "$file"

sed -i "/sub_filter \"src='\\/\\//a\\                sub_filter \"href='//\" \"\$processed_flag_attribute href='/main/\$relativescheme://\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"href='/\" \"\$processed_flag_attribute href='/main/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='https:\\/\\//a\\                sub_filter \"href='https://\" \"\$processed_flag_attribute href='/main/https://\";" "$file"
sed -i "/sub_filter \"src='http:\\/\\//a\\                sub_filter \"href='http://\" \"\$processed_flag_attribute href='/main/http://\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"import '/\" \"import '/main/js_/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"from '/\" \"from '/main/js_/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"import('\\/\" \"import('/main/js_/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"import( '\\/\" \"import( '/main/js_/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"fetch('\\/\" \"fetch('/main/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"fetch( '\\/\" \"fetch( '/main/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"'/cdn/\" \"'/main/\$dest_hostwithscheme/cdn/\";" "$file"

sed -i 's|# sub_filter_types text/html; already text/html by default but leaving it here for clarity|sub_filter_types text/css application/javascript text/javascript application/json;|' "$file"

handler="/opt/womginx/public/wombat-handler.js"
awk '
    /window\._womginx_WebSocket = window\.WebSocket;/ {
        print "        window._womginx_WebSocket = window.WebSocket;";
        print "        var womginxAppendOrigin = function (url) {";
        print "            var joiner = url.indexOf(\"?\") === -1 ? \"?\" : \"&\";";
        print "            return url + joiner + \"womginx_ws_origin_header=\" + dest_scheme + \"://\" + dest_host;";
        print "        };";
        print "        var womginxRewriteSocketUrl = function (url) {";
        print "            var raw = url && url.toString ? url.toString() : String(url);";
        print "            if (/^wss?:\\/\\//i.test(raw)) {";
        print "                return womginxAppendOrigin(proxy_prefix + proxy_path + \"ws_/\" + raw);";
        print "            }";
        print "            if (raw.charAt(0) === \"/\") {";
        print "                var wsScheme = dest_scheme === \"https\" ? \"wss://\" : \"ws://\";";
        print "                return womginxAppendOrigin(proxy_prefix + proxy_path + \"ws_/\" + wsScheme + dest_host + raw);";
        print "            }";
        print "            return womginxAppendOrigin(raw);";
        print "        };";
        print "        var womginxRewriteHttpUrl = function (url) {";
        print "            var raw = url && url.toString ? url.toString() : String(url);";
        print "            if (/^https?:\\/\\//i.test(raw)) return proxy_prefix + proxy_path + raw;";
        print "            if (raw.charAt(0) === \"/\") return proxy_prefix + proxy_path + dest_scheme + \"://\" + dest_host + raw;";
        print "            return raw;";
        print "        };";
        print "        window.WebSocket = function (url, protocols) {";
        print "            var rewrittenUrl = mergeDoubleSlash(womginxRewriteSocketUrl(url));";
        print "            if (protocols === undefined) return new window._womginx_WebSocket(rewrittenUrl);";
        print "            return new window._womginx_WebSocket(rewrittenUrl, protocols);";
        print "        };";
        print "        if (window.EventSource) {";
        print "            window._womginx_EventSource = window.EventSource;";
        print "            window.EventSource = function (url, eventSourceInitDict) {";
        print "                return new window._womginx_EventSource(mergeDoubleSlash(womginxRewriteHttpUrl(url)), eventSourceInitDict);";
        print "            };";
        print "        }";
        print "";
        print "        // Preserve native keyboard/input event semantics for React apps.";
        print "        _WBWombat.prototype.initUIEventsOverrides = function () { };";
        skip = 1;
        next;
    }
    skip {
        if ($0 ~ /^        };/) {
            skip = 0;
        }
        next;
    }
    { print }
' "$handler" > "$handler.tmp"
mv "$handler.tmp" "$handler"

sed -i 's|/main|/tor|g' "$file" /opt/womginx/public/wombat-handler.js /opt/womginx/public/index.html
