"""Settings tab — DB management, categories, users."""

import streamlit as st


def render(db, tx_svc, user_id: int) -> None:
    st.subheader("⚙️ Impostazioni")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 Statistiche")
        total_tx = len(db.get_transactions(limit=100_000))
        total_users = len(db.get_all_users())
        inv_tx = len(db.get_investment_transactions(user_id))
        positions = len(db.get_portfolio_positions(user_id))
        snaps = len(db.get_networth_snapshots(user_id))
        st.metric("Transazioni totali", f"{total_tx:,}")
        st.metric("Transazioni investimento", f"{inv_tx:,}")
        st.metric("Posizioni portafoglio", f"{positions:,}")
        st.metric("Snapshot patrimonio", f"{snaps:,}")
        st.metric("Utenti", total_users)

        st.divider()
        st.markdown("#### 🔧 Azioni Rapide")
        if st.button("🔄 Ricarica Categorie Default"):
            n = db.setup_default_categories()
            st.success(f"✅ {n} categorie aggiunte/aggiornate")
        if st.button("📋 Ricalcola Posizioni Portafoglio"):
            from investments import PortfolioService, ISINMapper
            ps = PortfolioService(db)
            positions = ps.recompute_positions(user_id)
            st.success(f"✅ {len(positions)} posizioni ricalcolate (FIFO)")

    with col2:
        st.markdown("#### 🗑️ Gestione Database")
        if st.button("🗑️ Reset Database", type="secondary"):
            st.session_state["show_reset_confirm"] = True

        if st.session_state.get("show_reset_confirm", False):
            st.warning("⚠️ **Questa operazione cancellerà TUTTI i dati!**")
            confirm_text = st.text_input("Digita 'CONFERMA' per procedere:")
            cy, cn = st.columns(2)
            with cy:
                if st.button("✅ Sì, cancella tutto", type="primary"):
                    if confirm_text == "CONFERMA":
                        db.reset_database()
                        st.success("🗑️ Database resettato!")
                        st.session_state["show_reset_confirm"] = False
                        st.rerun()
                    else:
                        st.error("Testo di conferma non corretto")
            with cn:
                if st.button("❌ Annulla"):
                    st.session_state["show_reset_confirm"] = False
                    st.rerun()

        st.divider()
        st.markdown("#### 📂 Categorie")
        with db.get_connection() as conn:
            cats = conn.execute(
                "SELECT name, category_type FROM categories WHERE parent_category_id IS NULL ORDER BY name"
            ).fetchall()
        if cats:
            for name, cat_type in cats:
                st.markdown(f"• **{name}** _{cat_type}_")
        else:
            if st.button("📥 Carica Categorie Default"):
                db.setup_default_categories()
                st.rerun()
