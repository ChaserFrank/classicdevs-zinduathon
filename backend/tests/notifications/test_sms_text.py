import pytest

from apps.notifications import sms_text
from apps.notifications.services import SMS_FOOTER, render_sms


def test_replaces_look_alikes_and_drops_non_gsm():
    assert sms_text.to_gsm("“Hi” – it’s… ok 🎉\tdone") == '"Hi" - it\'s... ok done'


def test_extended_characters_count_double():
    assert sms_text.gsm_length("a{b}€") == 1 + 2 + 1 + 2 + 2


def test_short_message_unchanged():
    assert (
        sms_text.compose("Hello", link="https://x.co/i", footer="Reply STOP")
        == "Hello https://x.co/i Reply STOP"
    )


def test_long_message_is_cut_but_link_and_footer_survive():
    link = "https://skillproof.app/inbox"
    text = sms_text.compose("word " * 80, link=link, footer=SMS_FOOTER)
    assert len(text) <= 160
    assert text.endswith(f"... {link} {SMS_FOOTER}")


def test_extended_chars_respected_in_budget():
    text = sms_text.compose("{" * 100, link="https://a.b", footer="")
    assert sms_text.gsm_length(text) <= 160


LONG = "Wanjiku-Nyambura Achieng'-Odhiambo " * 4  # deliberately absurd


@pytest.mark.parametrize(
    ("kind", "context"),
    [
        (
            "analysis_completed",
            {
                "score": 100,
                "top_skills": ["Django REST Framework" * 3],
                "tips": [LONG],
                "login": "a" * 39,
            },
        ),
        (
            "recruiter_feedback",
            {"company": LONG, "status_label": "Not a fit", "recruiter_name": LONG, "message": LONG},
        ),
        ("shortlisted", {"company": LONG, "stage_label": "Interview", "job_title": LONG}),
        ("recruiter_approved", {"company": LONG, "note": LONG}),
        ("recruiter_rejected", {"company": LONG, "note": LONG}),
    ],
)
def test_every_sms_template_fits_one_part_with_long_names(kind, context):
    link = "https://skillproof.app/u/" + "x" * 39
    text = render_sms(kind, {**context, "user": None, "link": link})
    assert sms_text.gsm_length(text) <= 160, text
    assert text == sms_text.to_gsm(text)  # only GSM-7 characters
    assert link in text and text.endswith(SMS_FOOTER)


def test_analysis_sms_matches_brief_example():
    text = render_sms(
        "analysis_completed",
        {
            "score": 72,
            "top_skills": ["TypeScript"],
            "tips": ["Add tests to shop-app"],
            "link": "https://sp.app/u/amina",
        },
    )
    assert text == (
        "SkillProof: your Signal Score is 72. Top skill: TypeScript. Tip: Add tests to shop-app. "
        "https://sp.app/u/amina Reply STOP to opt out"
    )


def test_sms_is_not_html_escaped():
    text = render_sms(
        "recruiter_feedback", {"company": "O'Reilly & Co", "status_label": "Interview", "link": ""}
    )
    assert "O'Reilly & Co" in text
