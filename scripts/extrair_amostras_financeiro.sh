#!/usr/bin/env bash
set -euo pipefail

REL="reports/V6-DOCUMENTOS-piloto-financeiro-v2.md"
OUT="reports/V6-FINANCEIRO-amostras.md"

# Quantas amostras por tipo queremos
N_DOC_FIN=10     # Documento Financeiro (fallback)
N_NF=5           # Nota Fiscal
N_EXTRATO=5      # Extrato Bancário
N_RECIBO=5       # Recibo de Salário/Holerite
N_COMPROV=5      # Comprovante de Transferência
N_IRPF=5         # Declaração de IRPF
N_FATURA=5       # Fatura

echo "# Amostras FINANCEIRO — V6" > "$OUT"
echo >> "$OUT"

extrair_por_tipo() {
  local tipo="$1"
  local n="$2"

  echo "## Tipo: $tipo" >> "$OUT"
  echo >> "$OUT"

  # Pega as linhas de tipo desejado e recua 3 linhas para pegar o bloco completo
  grep -n "/mnt/vault/documentos/FINANCEIRO/" "$REL" -n \
    | cut -d: -f1 \
    | while read L; do
        sed -n "$L,$((L+3))p" "$REL"
        echo
      done \
    | awk -v tipo="$tipo" '
        BEGIN { RS=""; FS="\n"; count=0 }
        {
          if ($0 ~ "tipo: " tipo) {
            print $0 "\n";
            count++;
          }
          if (count >= '"$n"') exit
        }
      ' >> "$OUT"

  echo >> "$OUT"
}

# Documento Financeiro (fallback)
extrair_por_tipo "Documento Financeiro" "$N_DOC_FIN"

# Outros tipos
extrair_por_tipo "Nota Fiscal" "$N_NF"
extrair_por_tipo "Extrato Bancário" "$N_EXTRATO"
extrair_por_tipo "Recibo de Salário/Holerite" "$N_RECIBO"
extrair_por_tipo "Comprovante de Transferência" "$N_COMPROV"
extrair_por_tipo "Declaração de IRPF" "$N_IRPF"
extrair_por_tipo "Fatura" "$N_FATURA"

echo "Amostras salvas em $OUT"
