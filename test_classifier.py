import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('classifier', ROOT / 'classify_langgraph_issues.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class ClassifierTests(unittest.TestCase):
    def classify(self, title='', body='', comments=None, repo='example/repo', number=1):
        comments = comments or []
        issue = {'number': number, 'title': title, 'body': body, 'comments': comments, 'comment_count': len(comments)}
        return c.classify_issue(issue, repo)['classification']

    def comment(self, text):
        return {'body': text, 'created_at': '2026-01-01', 'url': 'https://example.test/comment'}

    def test_system_info_is_not_cause(self):
        result = self.classify('The stream hangs', '### System Info\nOptional packages not installed\nPython 3.14')
        self.assertNotEqual(result['why_category'], 'setup_configuration')
        self.assertNotEqual(result['why_category'], 'dependency_platform')

    def test_template_checkbox_is_not_a_defect(self):
        result = self.classify(body='- [x] This is a bug, not a usage question.')
        self.assertEqual(result['why_category'], 'unclear')

    def test_distinct_evidence_for_categories(self):
        cases = [
            ('The filter returns the wrong result', 'product_defect'),
            ('I used the wrong configuration value', 'setup_configuration'),
            ('uvloop does not support Windows', 'dependency_platform'),
            ('The quickstart omits the required URL', 'documentation_gap'),
            ('Provide a way to configure streaming keys', 'feature_request'),
            ('requests 10 states when limit is 0', 'product_defect'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                result = self.classify(body=text)
                self.assertEqual(result['why_category'], expected)
                self.assertTrue(result['evidence']['matches'])

    def test_expected_actual_sections_are_compared(self):
        body = '### Expected behavior\nA limit of zero returns zero records.\n### Actual behavior\nIt returns ten records.'
        result = self.classify(body=body)
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertTrue(result['needs_review'])
        self.assertTrue(any(e['rule'] == 'reported_expected_actual_comparison' for e in result['evidence']['matches']))

    def test_documented_expectation_is_not_automatically_a_docs_gap(self):
        result = self.classify(body='The docstring describes the expected result. The filter returns the wrong result.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_title_only_is_flagged(self):
        result = self.classify(title='Provide a way to configure streaming keys')
        self.assertIn('classification_based_on_title_only', result['review_reasons'])

    def test_feature_with_expected_and_actual_behavior_is_reviewed_as_defect(self):
        result = self.classify(title='Provide a way to configure streaming keys',
                               body='### Expected behavior\nThe filter returns no records.\n### Actual behavior\nIt returns ten records.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertTrue(result['needs_review'])

    def test_questions_and_guesses_do_not_become_causes(self):
        for text in ('could this be caused by wrong configuration', 'maybe the cause was wrong configuration', 'is the issue caused by the wrong configuration'):
            with self.subTest(text=text):
                result = self.classify(comments=[self.comment(text)])
                self.assertEqual(result['why_category'], 'unclear')
                self.assertFalse(result['evidence']['comment_signals'][0]['used_for_category'])

    def test_explicit_comment_cause_is_traceable_and_reviewed(self):
        result = self.classify(comments=[self.comment('The cause was wrong configuration.')])
        self.assertEqual(result['why_category'], 'setup_configuration')
        self.assertIn('verify_comment_refers_to_this_issue', result['review_reasons'])
        self.assertEqual(result['evidence']['matches'][0]['source'], 'comment')

    def test_conflicting_comment_causes_are_unclear(self):
        result = self.classify(comments=[self.comment('The cause was wrong configuration.'), self.comment('The cause was a bug.')])
        self.assertEqual(result['why_category'], 'unclear')
        self.assertIn('conflicting_comment_causes', result['review_reasons'])

    def test_explicit_later_correction_can_resolve_comment_conflict(self):
        earlier = self.comment('The cause was a bug.')
        later = self.comment('The earlier diagnosis was wrong. The cause was wrong configuration.')
        later['created_at'] = '2026-01-02'
        result = self.classify(comments=[later, earlier])
        self.assertEqual(result['why_category'], 'setup_configuration')
        self.assertTrue(result['needs_review'])
        self.assertTrue(any(s['signal'] == 'superseded_by_explicit_correction'
                            for s in result['evidence']['comment_signals']))

    def test_pr_offer_does_not_make_a_defect_a_feature(self):
        result = self.classify(body='The filter returns the wrong result. I would like to contribute the focused fix.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_incidental_platform_does_not_prove_platform_cause(self):
        result = self.classify(body='The failure happens only on resume. System information: Windows.')
        self.assertNotEqual(result['why_category'], 'dependency_platform')

    def test_concrete_symptom_needs_report_corroboration(self):
        self.assertEqual(self.classify(title='The stream drops events')['why_category'], 'unclear')
        result = self.classify(title='The stream drops events',
                               body='The expected output contains two events. Instead only one is returned.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertTrue(any(e['source'] == 'title_and_body' for e in result['evidence']['matches']))

    def test_specific_locale_cause_is_not_just_system_metadata(self):
        result = self.classify(body='Actual: decoding depends on the machine locale; characters are corrupted on non-UTF-8 locales.')
        self.assertEqual(result['why_category'], 'dependency_platform')

    def test_test_command_issue_has_test_tooling_evidence(self):
        result = self.classify(title='make test ignores the TEST variable',
                               body='The Makefile test command runs all tests instead of the selected file.')
        self.assertEqual(result['why_category'], 'setup_configuration')

    def test_schema_violation_requires_explicit_input_evidence(self):
        result = self.classify(body='A node returns invalid state violating the declared schema.')
        self.assertEqual(result['why_category'], 'setup_configuration')
        self.assertTrue(any(e['rule'] == 'input_violates_declared_schema' for e in result['evidence']['matches']))

    def test_concrete_data_loss_is_traced(self):
        result = self.classify(body='The saved state is silently lost on load.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertTrue(any(e['rule'] == 'reported_data_loss' for e in result['evidence']['matches']))

    def test_bare_expected_label_is_not_an_evidence_pair(self):
        evidence = c.reproduction_evidence('The method returns a result.\nExpected:\n')
        self.assertFalse(any(e['rule'] == 'explicit_expected_and_reported_result' for e in evidence))

    def test_exception_title_without_support_stays_unclear(self):
        result = self.classify(title='TypeError from the operation', body='The operation is documented.')
        self.assertEqual(result['why_category'], 'unclear')

    def test_title_clue_does_not_override_report_evidence(self):
        result = self.classify(title='Incorrect quickstart',
                               body='### Expected behavior\nThe filter returns one record.\n'
                                    '### Actual behavior\nThe filter returns two records.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertIn('weaker_title_clue_differs', result['review_reasons'])
        title_evidence = next(e for e in result['evidence']['matches'] if e['source'] == 'title')
        self.assertEqual(title_evidence['strength'], 'weak')
        self.assertFalse(title_evidence['used_for_decision'])

    def test_explicit_comment_cause_can_clarify_symptom(self):
        result = self.classify(body='The filter returns the wrong result.',
                               comments=[self.comment('The cause was wrong configuration.')])
        self.assertEqual(result['why_category'], 'setup_configuration')
        self.assertEqual(result['evidence_strength'], 'strong')
        self.assertIn('verify_comment_refers_to_this_issue', result['review_reasons'])

    def test_reproduction_without_diagnosis_is_context_not_cause(self):
        result = self.classify(title='Add support for custom streaming',
                               comments=[self.comment('I reproduced this on current main.')])
        self.assertEqual(result['why_category'], 'feature_request')
        self.assertNotIn('comment_cause_needs_review', result['review_reasons'])
        signal = result['evidence']['comment_signals'][0]
        self.assertEqual(signal['signal'], 'reproduction_without_diagnosis')
        self.assertFalse(signal['used_for_category'])

    def test_unclassified_comment_cause_still_requires_review(self):
        result = self.classify(title='Add support for custom streaming',
                               comments=[self.comment('The root cause was a race between tasks.')])
        self.assertIn('comment_cause_needs_review', result['review_reasons'])

    def test_consistent_reported_failure_can_avoid_blanket_flag(self):
        result = self.classify(title='Cache ignores the expiry setting',
                               body='I expected cache expiry to preserve the configured timeout. '
                                    'Instead, cache expiry ignored the configured timeout.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertNotIn('reported_symptom_needs_confirmation', result['review_reasons'])
        self.assertIsNotNone(result['review_policy_note'])

    def test_platform_clue_keeps_symptom_review_flag(self):
        result = self.classify(title='Cache ignores expiry setting on Windows',
                               body='I expected cache expiry to preserve the configured timeout. '
                                    'Instead, cache expiry ignored the configured timeout.')
        self.assertIn('reported_symptom_needs_confirmation', result['review_reasons'])

    def test_preference_alone_is_flagged_for_feature_review(self):
        result = self.classify(title='Streaming behavior',
                               body='I would like to store additional stream metadata.')
        self.assertEqual(result['why_category'], 'feature_request')
        self.assertIn('feature_intent_needs_confirmation', result['review_reasons'])

    def test_wrong_existing_attributes_can_precede_feature_suggestion(self):
        result = self.classify(title='Streaming metadata',
                               body='The returned attributes are wrong. '
                                    'Please add support for custom metadata.')
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertIn('verify_existing_behavior_and_feature_request', result['review_reasons'])

    def test_wrong_output_value_is_not_misread_as_wrong_configuration(self):
        result = self.classify(body='The result is a silently wrong value with no error.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_generic_example_is_not_documentation(self):
        result = self.classify(body='For example, passing a missing key fails.')
        self.assertNotEqual(result['why_category'], 'documentation_gap')

    def test_feature_request_can_include_optional_implementation_suggestion(self):
        result = self.classify(title='Improve streaming',
                               body='I would like to add a stream option (perhaps with a setting).')
        self.assertEqual(result['why_category'], 'feature_request')

    def test_speculative_feature_wording_stays_unclear(self):
        result = self.classify(title='Streaming',
                               body='Perhaps this is a defect and I would like to know why.')
        self.assertEqual(result['why_category'], 'unclear')

    def test_title_symptom_may_end_with_fails_when_report_supports_it(self):
        result = self.classify(title='The streaming request fails',
                               body='The expected streaming result does not arrive.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_unimplemented_capability_is_a_feature_request(self):
        result = self.classify(title='Support custom stream validators',
                               body='Developers should be able to define custom validators, '
                                    'but the streaming API does not currently support custom validators.')
        self.assertEqual(result['why_category'], 'feature_request')

    def test_wrapped_explanation_keeps_meaning_across_adjacent_lines(self):
        text = 'The routing function returns a value that\nis not a key of the mapping.'
        self.assertTrue(any(e['category'] == 'setup_configuration' for e in c.rule_matches(text, 'body')))

    def test_wrapped_explanation_does_not_cross_heading(self):
        text = 'The routing function returns a value that\n### Different section\nis not a key of the mapping.'
        self.assertFalse(any(e['category'] == 'setup_configuration' for e in c.rule_matches(text, 'body')))

    def test_explicit_comment_cause_does_not_need_the_word_bug(self):
        result = self.classify(title='Checkpoint behavior',
                               comments=[self.comment("The root cause is a checkpoint that doesn't preserve state.")])
        self.assertEqual(result['why_category'], 'product_defect')
        self.assertIn('verify_comment_refers_to_this_issue', result['review_reasons'])

    def test_suggested_design_change_is_reviewable(self):
        result = self.classify(title='Make streaming behavior configurable',
                               body='Two changes to the stream API would remove the restriction.')
        self.assertEqual(result['why_category'], 'feature_request')

    def test_proposed_solution_does_not_prove_existing_failure(self):
        result = self.classify(title='Streaming', body='There is no configuration on the stream to change this.\n'
                               '## Ask\nReturn a new result instead of blocking until completion.')
        self.assertNotEqual(result['why_category'], 'product_defect')

    def test_question_about_a_comment_cause_is_not_used_as_diagnosis(self):
        result = self.classify(title='Streaming',
                               comments=[self.comment("Could the root cause be that it doesn't preserve state")])
        self.assertEqual(result['why_category'], 'unclear')
        self.assertFalse(result['evidence']['comment_signals'][0]['used_for_category'])

    def test_deleted_data_rule_requires_observation_in_report(self):
        title = 'Delete operations leave the deleted text in database files'
        self.assertEqual(self.classify(title=title, body='The operation completed.')['why_category'], 'unclear')
        result = self.classify(title=title, body='The database file still held the text after deletion.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_windows_metadata_alone_does_not_indicate_platform_cause(self):
        result = self.classify(title='Windows line endings', body='### System Info\nWindows 11')
        self.assertNotEqual(result['why_category'], 'dependency_platform')

    def test_desired_validator_is_not_automatically_a_setup_problem(self):
        result = self.classify(title='Support custom validators',
                               body='A custom validator rejects invalid input.')
        self.assertNotEqual(result['why_category'], 'setup_configuration')

    def test_repeating_weak_title_clues_does_not_make_them_strong(self):
        result = self.classify(title='Incorrect quickstart. Incorrect README.',
                               body='### Expected behavior\nThe filter returns one record.\n'
                                    '### Actual behavior\nThe filter returns two records.')
        self.assertEqual(result['why_category'], 'product_defect')

    def test_classification_runs_without_reference_for_another_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            raw = directory / 'raw.json'
            raw.write_text(json.dumps({'source_repository': 'another/project', 'issues': [
                {'number': 9649, 'title': 'Result', 'body': 'The filter returns the wrong result.',
                 'comment_count': 0, 'comments': []}]}), encoding='utf-8')
            output = directory / 'processed'
            subprocess.run([sys.executable, str(ROOT / 'classify_langgraph_issues.py'),
                            '--input', str(raw), '--output-dir', str(output)], check=True, capture_output=True)
            result = json.loads((output / 'langgraph_open_issues_classified.json').read_text(encoding='utf-8'))
            self.assertEqual(result['classification_summary']['human_issue_records'], 1)
            self.assertEqual(result['issues'][0]['classification']['why_category'], 'product_defect')
            self.assertEqual(len(list((output / 'by_category').glob('*.json'))), 6)

    def test_exclusion_is_repository_specific(self):
        self.assertTrue(self.classify(repo='LANGCHAIN-AI/LANGGRAPH', number=9649)['excluded_from_human_count'])
        self.assertFalse(self.classify(repo='other/repo', number=9649)['excluded_from_human_count'])

    def test_multiple_marker_without_count(self):
        result = self.classify(body='Several distinct bugs are reported.')
        self.assertTrue(result['contains_multiple_problems'])
        self.assertIsNone(result['additional_problem_count'])

    def test_raw_reference_cases(self):
        source = json.loads((ROOT / 'data/raw/langgraph_open_issues_with_comments.json').read_text(encoding='utf-8'))
        for number, expected in [(9645, 'feature_request'), (9620, 'product_defect'), (9660, 'setup_configuration'), (9607, 'product_defect'), (7814, 'dependency_platform'), (9577, 'documentation_gap'), (6798, 'feature_request')]:
            with self.subTest(number=number):
                issue = next(i for i in source['issues'] if i['number'] == number)
                self.assertEqual(c.classify_issue(issue, source['source_repository'])['classification']['why_category'], expected)
        issue = next(i for i in source['issues'] if i['number'] == 9655)
        result = c.classify_issue(issue, source['source_repository'])['classification']
        self.assertEqual(result['additional_problem_count'], 13)
        self.assertEqual(len(result['problem_details']), 14)

    def test_examples_from_earlier_manual_review(self):
        source = json.loads((ROOT / 'data/raw/langgraph_open_issues_with_comments.json').read_text(encoding='utf-8'))
        cases = [(8870, 'product_defect'), (7990, 'feature_request'),
                 (9603, 'setup_configuration'), (9414, 'setup_configuration'),
                 (9320, 'dependency_platform'), (9541, 'dependency_platform'),
                 (9592, 'product_defect'), (9304, 'product_defect'),
                 (6494, 'unclear'), (6447, 'unclear'), (6171, 'unclear'),
                 (8366, 'unclear'), (1266, 'unclear')]
        for number, expected in cases:
            with self.subTest(number=number):
                issue = next(i for i in source['issues'] if i['number'] == number)
                self.assertEqual(c.classify_issue(issue, source['source_repository'])['classification']['why_category'], expected)
        issue = next(i for i in source['issues'] if i['number'] == 8746)
        result = c.classify_issue(issue, source['source_repository'])['classification']
        self.assertEqual(result['additional_problem_count'], 2)
        self.assertEqual(len(result['problem_details']), 3)

    def test_metadata_and_code_issue_count_are_not_separate_problems(self):
        result = self.classify(body='A field is missing from the filtered result.\n**Root cause**: Two issues in the implementation produce this failure.')
        self.assertFalse(result['contains_multiple_problems'])
        self.assertNotEqual(result['why_category'], 'setup_configuration')

    def test_platform_and_project_links_do_not_decide_cause(self):
        result = self.classify(body='The failure appears only on resume. The missing-issue-link workflow closed the pull request.')
        self.assertNotIn(result['why_category'], ('dependency_platform', 'documentation_gap'))

if __name__ == '__main__':
    unittest.main()
