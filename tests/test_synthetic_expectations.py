# -*- coding: utf-8 -*-
"""Sentetik izin tanımının kendi iç tutarlılığı — leak testinin 'beklenen' tarafı
yanlışsa leak testi de anlamsızlaşır; bu testler o hesabı sabitler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import synthetic_corpus as corpus


def test_zeynep_sees_restricted_ik():
    pages = corpus.expected_allowed_pages("zeynep")
    assert "ik-maas-bantlari" in pages
    assert "ik-isten-cikis" in pages


def test_ayse_cannot_see_restricted_ik():
    pages = corpus.expected_allowed_pages("ayse")
    assert "ik-yillik-izin" in pages
    assert "ik-maas-bantlari" not in pages


def test_mehmet_no_fin_access():
    assert "FIN" not in corpus.expected_allowed_spaces("mehmet")
    assert not any(p.startswith("fin-") for p in corpus.expected_allowed_pages("mehmet"))


def test_mehmet_cannot_see_security_page():
    assert "eng-guvenlik-acigi" not in corpus.expected_allowed_pages("mehmet")


def test_deniz_sees_security_page():
    assert "eng-guvenlik-acigi" in corpus.expected_allowed_pages("deniz")


def test_elif_sees_restricted_fin():
    assert "fin-tedarikci-odeme" in corpus.expected_allowed_pages("elif")


def test_can_cannot_see_restricted_fin():
    assert "fin-tedarikci-odeme" not in corpus.expected_allowed_pages("can")
    assert "fin-masraf" in corpus.expected_allowed_pages("can")


def test_everyone_sees_public_ik():
    for user in corpus.USERS:
        assert "IK" in corpus.expected_allowed_spaces(user)
        assert "ik-yillik-izin" in corpus.expected_allowed_pages(user)


# --- G-2 genişletmesi: yeni kısıtlı sayfalar aynı kısıt semantiğine uymalı ---


def test_new_restricted_prim_only_ik_yonetim():
    # zeynep ik-yonetim; mehmet IK space'i görür ama bu kısıtlı sayfayı görmez
    assert "ik-prim-politikasi" in corpus.expected_allowed_pages("zeynep")
    assert "ik-prim-politikasi" not in corpus.expected_allowed_pages("mehmet")
    assert "ik-prim-politikasi" not in corpus.expected_allowed_pages("ayse")


def test_new_restricted_veri_siniflandirma_only_guvenlik():
    # deniz guvenlik; mehmet ENG space'i görür ama bu kısıtlı sayfayı görmez
    assert "eng-veri-siniflandirma" in corpus.expected_allowed_pages("deniz")
    assert "eng-veri-siniflandirma" not in corpus.expected_allowed_pages("mehmet")


def test_new_restricted_bordro_only_fin_yonetim():
    # elif fin-yonetim; can FIN space'i görür ama bordroyu görmez
    assert "fin-bordro" in corpus.expected_allowed_pages("elif")
    assert "fin-bordro" not in corpus.expected_allowed_pages("can")


def test_corpus_size_and_unique_keys():
    assert len(corpus.PAGES) == 40
    keys = [p["page_key"] for p in corpus.PAGES]
    assert len(keys) == len(set(keys)), "page_key'ler benzersiz olmalı"


def test_new_public_pages_visible_to_space_members():
    # confusable küme örnekleri: yeni herkese açık sayfalar space üyelerine görünür
    assert "ik-dogum-izni" in corpus.expected_allowed_pages("ayse")
    assert "eng-parola-politikasi" in corpus.expected_allowed_pages("mehmet")
    assert "fin-seyahat" in corpus.expected_allowed_pages("can")
