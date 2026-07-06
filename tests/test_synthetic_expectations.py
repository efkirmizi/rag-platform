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
