"""Imports tab — provider upload, preview, import."""

import json

import pandas as pd
import streamlit as st

from dashboard.components.kpi_cards import fmt_eur
from providers import PROVIDERS


def render(db, tx_svc, user_id: int, cat_svc) -> None:
    st.subheader("📥 Importa Transazioni")

    col_upload, col_info = st.columns([3, 1])
    with col_upload:
        provider_name = st.selectbox(
            "Provider",
            list(PROVIDERS.keys()),
            format_func=lambda x: PROVIDERS[x].bank_label,
        )
        f = st.file_uploader("Seleziona file (CSV / XLSX)", type=["csv", "xlsx"])

    with col_info:
        st.markdown("#### Provider disponibili")
        for name, p in PROVIDERS.items():
            st.markdown(f"• **{p.bank_label}**")

    if f:
        provider = PROVIDERS[provider_name]
        try:
            preview_data = list(provider.parse(f))
        except Exception as e:
            st.error(f"Errore nel parsing: {e}")
            return

        for t in preview_data:
            t["_categoria_suggerita"] = cat_svc.categorize(
                t.get("description", ""), t.get("detail"), t.get("category_hint")
            )

        st.success(f"✅ Rilevato: **{provider.bank_label}** — {len(preview_data)} transazioni trovate")

        st.markdown("#### Anteprima (prime 10)")
        prev_df = pd.DataFrame(preview_data[:10])
        if not prev_df.empty and "amount" in prev_df.columns:
            prev_df["Importo"] = prev_df["amount"].apply(fmt_eur)
        show_cols = [c for c in ["transaction_date", "description", "Importo", "transaction_type",
                                  "isin", "_categoria_suggerita"] if c in prev_df.columns]
        st.dataframe(
            prev_df[show_cols].rename(columns={
                "transaction_date": "Data", "description": "Descrizione",
                "transaction_type": "Tipo", "isin": "ISIN", "_categoria_suggerita": "Categoria suggerita",
            }),
            use_container_width=True,
            hide_index=True,
        )

        f.seek(0)
        col_btn, col_space = st.columns([1, 3])
        with col_btn:
            if st.button("🚀 Importa in DB", type="primary"):
                provider = PROVIDERS[provider_name]
                inserted = 0
                for t in provider.parse(f):
                    bank = getattr(provider, "bank_label", provider_name)
                    cat = cat_svc.categorize(
                        t.get("description", ""), t.get("detail"), t.get("category_hint")
                    )
                    tx_type = t.get("transaction_type", "expense")

                    # Use extended upsert for investment transactions
                    if tx_type == "investment":
                        from core.database import DatabaseManager
                        ok, tx_id = db.upsert_investment_transaction(user_id, {
                            **t,
                            "user_id": user_id,
                            "original_data": json.dumps(t.get("original", {}), ensure_ascii=False),
                        })
                    else:
                        ok, tx_id = db.upsert_transaction_if_new(
                            user_id,
                            t["transaction_date"],
                            t["amount"],
                            t["description"],
                        )
                        if tx_id and tx_id > 0:
                            meta = {
                                "source": provider_name, "bank": bank,
                                "detail": t.get("detail", ""),
                                "category_hint": t.get("category_hint", ""),
                                "original": t.get("original", {}),
                                "amount_raw": t.get("amount_raw"),
                                "account": t.get("account"),
                                "currency": t.get("currency"),
                            }
                            tx_svc.update_metadata(
                                tx_id,
                                import_source=provider_name,
                                original_data=json.dumps(meta, ensure_ascii=False),
                                payee=t["description"],
                                notes=t.get("detail") or None,
                            )
                            # Apply source_bank and transaction_type to non-investment tx
                            with db.get_connection() as conn:
                                conn.execute(
                                    "UPDATE transactions SET source_bank=?, transaction_type=? WHERE id=?",
                                    (t.get("source_bank", bank), tx_type, tx_id),
                                )
                                conn.commit()
                            if cat:
                                existing = db.get_category_by_name(cat)
                                if existing:
                                    tx_svc.update_classification(tx_id, category_id=existing["id"])
                    if ok:
                        inserted += 1

                st.success(f"✅ Import completato: **{inserted} nuove transazioni** su {len(preview_data)} totali.")
                st.rerun()
