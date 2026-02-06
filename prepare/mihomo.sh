mkdir -p ~/mihomo && cd ~/mihomo
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.1/mihomo-linux-amd64-v1.18.1.gz
wget https://github.com/Dreamacro/maxmind-geoip/releases/latest/download/Country.mmdb
gzip -d mihomo-linux-amd64-v1.18.1.gz
mv mihomo-linux-amd64-v1.18.1 mihomo
chmod +x mihomo

touch config.yaml

./mihomo -d .