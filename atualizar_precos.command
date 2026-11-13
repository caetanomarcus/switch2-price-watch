#!/bin/bash
set -e
cd "$(dirname "$0")"

# Usa o Python do sistema (/usr/bin/python3) em vez do "python3" do PATH,
# porque se você tiver o Anaconda/Miniconda ativado (prompt mostrando
# "(base)"), o "python3" do PATH aponta pra versão do Conda - que pode
# ser tão nova que pacotes como o "greenlet" (dependência do Playwright)
# ainda não têm instalador pré-compilado pra ela, e a instalação falha
# tentando compilar do zero. O Python do sistema é mais estável pra isso.
PY=/usr/bin/python3
if [ ! -x "$PY" ]; then
  PY=python3
fi
echo "Usando: $($PY --version) ($PY)"

echo "=== Switch 2 Price Watch - atualização local ==="
echo ""

# O Python do sistema do macOS não vem com o pip instalado por padrão.
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  echo "Instalando o pip (primeira vez)..."
  "$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
fi

echo "1/4 - Instalando dependências Python (rápido se já instalado)..."
"$PY" -m pip install --quiet --user -r requirements.txt

echo "2/4 - Instalando navegador do Playwright (só demora na primeira vez)..."
"$PY" -m playwright install chromium

echo "3/4 - Rodando o scraper (Mercado Livre, Kabum, Magalu, Amazon)..."
"$PY" scraper.py

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
