#!/bin/bash
# usage: ovq.sh query_file out_file
Q="$1"; OUT="$2"; delay=20
for i in $(seq 1 12); do
  code=$(curl -sS -m 420 -A "no-one-is-an-island/1.0" --data-urlencode "data@$Q" -o "$OUT.tmp" -w "%{http_code}" "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
  sz=$(stat -c %s "$OUT.tmp" 2>/dev/null || echo 0)
  echo "$(date +%T) try $i: HTTP $code size $sz" >&2
  if [ "$code" = "200" ] && head -c 200 "$OUT.tmp" | grep -q '"elements"\|"version"'; then
    if grep -q '"remark"' "$OUT.tmp"; then echo "REMARK: $(grep -o '"remark"[^}]*' "$OUT.tmp" | head -c 400)" >&2; fi
    mv "$OUT.tmp" "$OUT"; exit 0
  fi
  head -c 300 "$OUT.tmp" >&2; echo >&2
  sleep $delay; delay=$((delay*2)); [ $delay -gt 120 ] && delay=120
done
exit 1
