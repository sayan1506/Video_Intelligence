from models.schemas import progress_to_stage, PROGRESS_STAGES


class TestProgressToStage:

    def test_progress_0_is_queued(self):
        assert progress_to_stage(0) == "Queued"

    def test_progress_10_is_uploading(self):
        assert progress_to_stage(10) == "Uploading video..."

    def test_progress_25_is_queued_for_processing(self):
        assert progress_to_stage(25) == "Queued for processing"

    def test_progress_50_is_transcribing(self):
        assert progress_to_stage(50) == "Transcribing audio..."

    def test_progress_75_is_detecting_scenes(self):
        assert progress_to_stage(75) == "Detecting scenes..."

    def test_progress_90_is_generating_summary(self):
        assert progress_to_stage(90) == "Generating summary..."

    def test_progress_100_is_completed(self):
        assert progress_to_stage(100) == "Completed"

    def test_progress_60_maps_to_last_completed_stage(self):
        # 60 is between 50 and 75 — should map to stage 50
        assert progress_to_stage(60) == "Transcribing audio..."

    def test_progress_30_maps_to_stage_25(self):
        assert progress_to_stage(30) == "Queued for processing"

    def test_failed_status_overrides_progress(self):
        # Even progress=90 should show "Processing failed" if status=failed
        assert progress_to_stage(90, status="failed") == "Processing failed"

    def test_completed_status_shows_completed(self):
        assert progress_to_stage(100, status="completed") == "Completed"

    def test_all_defined_stage_keys_map_exactly(self):
        # Every key in PROGRESS_STAGES should map to its own label exactly
        for progress_val, expected_label in PROGRESS_STAGES.items():
            assert progress_to_stage(progress_val) == expected_label