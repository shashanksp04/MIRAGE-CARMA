from io import BytesIO
import json
import re

from PIL import Image
import pytest


def expect():
    return pytest.importorskip("playwright.sync_api").expect


def submit(page, question):
    page.get_by_role("button", name="Custom question", exact=True).click()
    page.get_by_role("textbox", name="What would you like to know?").fill(question)
    page.get_by_role("button", name="Run question", exact=True).click()


def completed(page):
    page.wait_for_function("document.querySelector('#run-state').textContent === 'Completed'")
    page.wait_for_function("document.querySelector('#launch-hint').textContent.includes('Ready to follow')")


def test_desktop_retrieval_details_safe_answer_mobile_and_keyboard(page):
    check = expect()
    positions = [page.locator(selector).bounding_box()["x"] for selector in (".input-panel", ".timeline-panel", ".details-panel")]
    assert positions == sorted(positions) and len(set(positions)) == 3
    page.screenshot(path="/tmp/mirage-phase3-desktop.png", full_page=True)
    submit(page, "TEST direct retrieval question")
    completed(page)
    check(page.locator("#result")).to_contain_text("TEST FIXTURE RESPONSE")
    check(page.locator("#result strong").first).to_have_text("Evidence-informed guidance")
    assert page.evaluate("window.injected") is None
    assert page.locator('a[href^="javascript:"]').count() == 0
    page.locator(".stage-button").filter(has_text="Evidence retrieval").click()
    check(page.locator("#stage-details table")).to_contain_text("0.725")
    check(page.locator("#stage-details table")).to_contain_text("Selected")
    check(page.locator("#stage-details table")).to_contain_text("Rejected")
    page.locator(".stage-button").filter(has_text="Evidence confidence").click()
    assert page.locator("#stage-details meter").count() == 4
    check(page.locator("#stage-details")).to_contain_text("High ≥ 0.780")
    page.screenshot(path="/tmp/mirage-phase3-result-fixture.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    boxes = [page.locator(selector).bounding_box() for selector in (".input-panel", ".timeline-panel", ".details-panel")]
    assert boxes[0]["y"] < boxes[1]["y"] < boxes[2]["y"]
    page.screenshot(path="/tmp/mirage-phase3-mobile.png", full_page=True)
    page.get_by_role("button", name="Clear view", exact=True).focus()
    page.keyboard.press("Enter")
    check(page.locator("#timeline-empty")).to_be_visible()


def test_augmentation_loops_diagnostics_counts_and_confirmation(page, browser_server):
    check = expect()
    submit(page, "TEST augment question")
    completed(page)
    assert page.locator(".stage-button").filter(has_text="Evidence retrieval").count() == 2
    assert page.locator(".timeline-item.status-failed").count() == 0
    check(page.locator("#diagnostics")).to_be_visible()
    check(page.locator("#runtime-delta")).to_contain_text("+2 chunks")
    page.locator(".stage-button").filter(has_text="Web search").click()
    check(page.locator("#stage-details")).to_contain_text("corn guidance site:example.edu")
    check(page.locator("#stage-details")).to_contain_text("TEST FIXTURE web source")
    page.locator(".stage-button").filter(has_text="Evidence confidence").first.click()
    check(page.locator("#stage-details")).to_contain_text("Web search was subsequently invoked")
    page.get_by_role("button", name="Clear demo runtime…").click()
    check(page.get_by_role("dialog")).to_contain_text("2 chunks")
    check(page.get_by_role("button", name="Clear runtime", exact=True)).to_be_disabled()
    page.get_by_label(re.compile("Type.*to confirm")).fill("CLEAR mirage_base")
    check(page.get_by_role("button", name="Clear runtime", exact=True)).to_be_disabled()
    page.get_by_label(re.compile("Type.*to confirm")).fill("CLEAR mirage_demo_runtime")
    page.get_by_role("button", name="Clear runtime", exact=True).click()
    check(page.get_by_role("dialog")).not_to_be_visible()
    assert browser_server.control.clear_count == 1
    assert browser_server.database.points == 0
    check(page.locator("#result")).to_contain_text("TEST FIXTURE RESPONSE")


def test_identification_image_and_input_preservation(page, browser_server):
    check = expect()
    page.get_by_label("Start with a question").select_option("identification-image")
    check(page.get_by_role("button", name="Run question", exact=True)).to_be_disabled()
    image = BytesIO()
    Image.new("RGB", (32, 24), "green").save(image, format="PNG")
    page.locator("#images").set_input_files({"name": "leaf.png", "mimeType": "image/png", "buffer": image.getvalue()})
    check(page.locator("#image-count")).to_have_text("1 / 3")
    page.get_by_role("button", name="Run question", exact=True).click()
    completed(page)
    check(page.locator("#query-context")).to_contain_text("Visual observations · retrieval only")
    page.locator("#query-context").get_by_text("Visual observations · retrieval only", exact=True).click()
    check(page.locator("#query-context")).to_contain_text("TEST OBSERVATIONS")
    assert page.locator(".workspace-grid > .panel").count() == 3
    assert page.locator("#query-context img").count() == 1
    assert page.locator("#query-context img").evaluate("image => image.complete && image.naturalWidth > 0")
    assert len(browser_server.control.generated[0]["images"]) == 1
    assert "TEST OBSERVATIONS" not in browser_server.control.generated[0]["query"]


def test_insufficient_and_failed_outcomes_never_show_unsupported_answer(page, browser_server):
    check = expect()
    submit(page, "TEST insufficient evidence")
    page.wait_for_function("document.querySelector('#run-state').textContent === 'Insufficient evidence'")
    check(page.locator("#result")).to_contain_text("More reliable evidence is needed")
    assert not browser_server.control.generated
    check(page.locator("#result")).not_to_contain_text("TEST FIXTURE RESPONSE")
    page.get_by_role("button", name="Clear view", exact=True).click()
    page.wait_for_function("!document.querySelector('#query-fields').disabled")
    submit(page, "TEST generation failure")
    page.wait_for_function("document.querySelector('#run-state').textContent === 'Failed'")
    check(page.locator("#result")).to_contain_text("The question could not be completed")
    check(page.locator("#result")).not_to_contain_text("TEST FIXTURE RESPONSE")


def test_reload_restores_active_run_clear_view_does_not_cancel(page, browser_server):
    check = expect()
    submit(page, "TEST hold for restore")
    page.wait_for_function("document.querySelector('#query-context').textContent.includes('TEST hold')")
    check(page.locator("#question")).to_be_disabled()
    check(page.get_by_role("button", name="Clear demo runtime…")).to_be_disabled()
    page.reload()
    page.wait_for_function("document.querySelector('#query-context').textContent.includes('TEST hold')")
    check(page.locator("#run-state")).to_have_text("Running")
    page.get_by_role("button", name="Clear view", exact=True).click()
    check(page.locator("#timeline-empty")).to_be_visible()
    check(page.locator("#notice")).to_contain_text("continues on the server")
    page.wait_for_function("!document.querySelector('#follow-active-run').hidden")
    page.get_by_role("button", name="Follow active run", exact=True).click()
    browser_server.control.gate.set()
    page.wait_for_function("document.querySelector('#run-state').textContent === 'Completed'")
    assert len(browser_server.control.generated) == 1


def test_browser_recovers_truncated_stream_from_last_sequence(page):
    intercepted = []
    def truncate_once(route):
        intercepted.append(route.request.url)
        if len(intercepted) > 1:
            route.continue_()
            return
        response = route.fetch()
        frames = response.text().split("\n\n")
        route.fulfill(status=200, content_type="text/event-stream", body="\n\n".join(frames[:2]) + "\n\n")
    page.route("**/api/runs/*/events?*", truncate_once)
    submit(page, "TEST stream reconnect")
    completed(page)
    assert len(intercepted) >= 2
    assert "after=2" in intercepted[1]
    expect()(page.locator("#result")).to_contain_text("TEST FIXTURE RESPONSE")


def test_missing_services_disable_launch_and_explain_readiness(page, browser_server):
    check = expect()
    browser_server.control.ready = False
    page.locator("#health-panel > summary").click()
    page.get_by_role("button", name="Refresh services", exact=True).click()
    page.wait_for_function("document.querySelector('#health-summary').textContent.includes('attention')")
    page.get_by_role("button", name="Custom question", exact=True).click()
    page.get_by_role("textbox", name="What would you like to know?").fill("Question")
    check(page.get_by_role("button", name="Run question", exact=True)).to_be_disabled()
    check(page.locator("#health-checks")).to_contain_text("Not ready")


def test_custom_configuration_snapshot_readiness_and_preset_reset(page):
    check = expect()
    page.locator("#custom-configuration").check()
    assert page.locator("#custom-configuration").bounding_box()["width"] <= 22
    page.locator("#workflow").select_option("ablation_5_uncertainty_aware_rag")
    page.locator("#custom-db").uncheck()
    page.locator("#custom-crop").uncheck()
    page.wait_for_function("document.querySelector('#feature-list').textContent.includes('Web search · off') && document.querySelector('#health-summary').textContent.includes('Services ready')")
    submit(page, "TEST custom configuration retrieval")
    completed(page)
    run_id = page.evaluate("sessionStorage.getItem('mirage-active-run')")
    record = page.request.get(f"{page.url.rstrip(chr(47))}/api/runs/{run_id}").json()
    config = record["metadata"]["config"]
    assert config["custom"]
    assert config["instruction_preset_id"] == "ablation_5_uncertainty_aware_rag"
    assert not config["db_on"] and not config["crop_dict_on"] and not config["web_search_on"]
    assert config["confidence_on"]
    assert record["result"]["config"] == config
    page.locator("#preset").select_option("ablation_2_static_rag")
    check(page.locator("#custom-configuration")).not_to_be_checked()
    check(page.locator("#custom-controls")).to_be_hidden()
    check(page.locator("#feature-list")).to_contain_text("Confidence evaluation · off")
    check(page.locator("#query-context")).to_contain_text("Custom configuration")
    assert page.request.get(f"{page.url.rstrip(chr(47))}/api/runs/{run_id}").json()["metadata"]["config"] == config
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#custom-configuration").check()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_history_and_replay_work_with_inference_unavailable(page, browser_server):
    check = expect()
    submit(page, 'TEST direct retrieval recording')
    completed(page)
    page.locator('#refresh-history').click()
    page.wait_for_function("document.querySelector('#history-run').options.length > 0")
    page.locator('#reset-view').click()
    browser_server.control.ready = False
    page.locator('#replay-history').click()
    check(page.locator('#execution-mode')).to_contain_text('REPLAY')
    page.wait_for_function("document.querySelector('#run-state').textContent === 'Completed'")
    check(page.locator('#result')).to_contain_text('TEST FIXTURE RESPONSE')
    check(page.locator('#execution-mode')).to_contain_text('REPLAY')
    page.locator('#inspect-history').click()
    check(page.locator('#execution-mode')).to_contain_text('Saved execution')
