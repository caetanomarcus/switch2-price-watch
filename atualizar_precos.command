#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Switch 2 Price Watch - atualização local ==="
echo ""
echo "1/4 - Instalando dependências Python (rápido se já instalado)..."
pip3 install --quiet --user -r requirements.txt

echo "2/4 - Instalando navegador do Playwright (só demora na primeira vez)..."
python3 -m playwright install chromium

echo "3/4 - Rodando o scraper (Mercado Livre, Kabum, Magalu, Amazon)..."
python3 scraper.py

echo "4/4 - Enviando atualização pro GitHub..."
git add data/prices.json
if git diff --cached --quiet; then
  echo "Nenhuma mudança nos preços desde a última vez."
else
  git commit -m "chore: atualiza precos via scraper local ($(date +%Y-%m-%d))"
  git push
  echo ""
  echo "Preços atualizados! Site: https://caetanomarcus.github.io/switch2-price-watch/"
fi

echo ""
echo "Concluído. Pressione qualquer tecla para fechar esta janela."
read -n 1 -s
