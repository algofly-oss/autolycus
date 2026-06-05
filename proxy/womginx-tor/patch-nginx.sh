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

sed -i "/sub_filter 'src=\\\"\\/\\//a\\                sub_filter 'href=\\\"//' '\$processed_flag_attribute href=\\\"/main/\$relativescheme://';" "$file"
sed -i "/sub_filter 'src=\\\"\\/'/a\\                sub_filter 'href=\\\"/' '\$processed_flag_attribute href=\\\"/main/\$dest_hostwithscheme/';" "$file"
sed -i "/sub_filter 'src=\\\"https:\\/\\//a\\                sub_filter 'href=\\\"https://' '\$processed_flag_attribute href=\\\"/main/https://';" "$file"
sed -i "/sub_filter 'src=\\\"http:\\/\\//a\\                sub_filter 'href=\\\"http://' '\$processed_flag_attribute href=\\\"/main/http://';" "$file"

sed -i "/sub_filter \"src='\\/\\//a\\                sub_filter \"href='//\" \"\$processed_flag_attribute href='/main/\$relativescheme://\";" "$file"
sed -i "/sub_filter \"src='\\//a\\                sub_filter \"href='/\" \"\$processed_flag_attribute href='/main/\$dest_hostwithscheme/\";" "$file"
sed -i "/sub_filter \"src='https:\\/\\//a\\                sub_filter \"href='https://\" \"\$processed_flag_attribute href='/main/https://\";" "$file"
sed -i "/sub_filter \"src='http:\\/\\//a\\                sub_filter \"href='http://\" \"\$processed_flag_attribute href='/main/http://\";" "$file"

sed -i 's|/main|/tor|g' "$file" /opt/womginx/public/wombat-handler.js /opt/womginx/public/index.html
