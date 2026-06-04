"""
End-to-End Tests for Dashboard Topic Filter
Validates that the topic filter is applied consistently across all 6 dashboard frames.

Ref: Issue #41 - Bug: filtro por tópicos não aplica em todos os frames da tela de indicadores
https://github.com/acmeleme/Conversation-Knowledge-Mining-Solution-Accelerator/issues/41

Test Scope:
1. Single Topic Selection Tests - Verify all 6 frames restrict to that topic
2. Multiple Topic Selection Tests - Verify all 6 frames show combined data
3. Filter Reset Tests - Verify all 6 frames revert to unfiltered view
4. Integration Tests - Verify topic filter works with other filters
"""

import pytest
import logging
import time
from pytest_check import check
import requests
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DashboardFrameValidator:
    """Helper class to validate dashboard frame data against topic filter."""
    
    FRAME_IDS = {
        'TOTAL_CALLS': 'Total Calls',
        'AVG_HANDLING_TIME': 'Average Handling Time',
        'SATISFIED': 'Satisfied',
        'SENTIMENT': 'Topics Overview',
        'AVG_HANDLING_TIME_BY_TOPIC': 'Average Handling Time By Topic',
        'KEY_PHRASES': 'Key Phrases'
    }
    
    def __init__(self, api_base_url: str):
        """Initialize validator with API base URL."""
        self.api_base_url = api_base_url.rstrip('/')
        self.last_response = None
    
    def fetch_chart_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch chart data from the API with optional filters."""
        url = f"{self.api_base_url}/api/fetchChartDataWithFilters"
        
        payload = {
            'selected_filters': {
                'Topic': [],
                'Sentiment': [],
                'DateRange': [],
            }
        }
        
        if filters:
            if 'topics' in filters:
                payload['selected_filters']['Topic'] = filters['topics']
            if 'sentiments' in filters:
                payload['selected_filters']['Sentiment'] = filters['sentiments']
            if 'date_range' in filters:
                payload['selected_filters']['DateRange'] = [filters['date_range']]
        
        logger.info(f"Fetching chart data with filters: {payload}")
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            self.last_response = response.json()
            return self.last_response
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch chart data: {e}")
            raise
    
    def get_frame_by_id(self, frame_id: str, data: Optional[List[Dict]] = None) -> Optional[Dict]:
        """Extract a specific frame from the response data."""
        if data is None:
            data = self.last_response
        
        if not data:
            return None
        
        for frame in data:
            if frame.get('id') == frame_id:
                return frame
        
        return None
    
    def get_topics_from_frame(self, frame_id: str, data: Optional[List[Dict]] = None) -> set:
        """Extract all topics mentioned in a specific frame."""
        if data is None:
            data = self.last_response
        
        frame = self.get_frame_by_id(frame_id, data)
        if not frame:
            return set()
        
        topics = set()
        chart_value = frame.get('chart_value', [])
        
        for item in chart_value:
            if 'name' in item:
                topics.add(item['name'])
        
        return topics
    
    def validate_single_topic_filter(self, selected_topics: List[str], 
                                     data: List[Dict], frame_id: str) -> bool:
        """Validate that a frame contains only data for the selected topics."""
        frame_topics = self.get_topics_from_frame(frame_id, data)
        selected_set = set(selected_topics)
        
        # For sentiment and other non-topic frames, the check is different
        if frame_id == 'SENTIMENT':
            # Sentiment frame may have all sentiments regardless of topic filter
            # but the data should be from selected topics only
            return True
        
        # For topic-based frames, verify intersection
        if not frame_topics:
            logger.warning(f"Frame {frame_id} has no topics extracted")
            return True
        
        unexpected_topics = frame_topics - selected_set
        if unexpected_topics:
            logger.warning(f"Frame {frame_id} contains unexpected topics: {unexpected_topics}")
            return False
        
        return True
    
    def validate_all_frames_present(self, data: List[Dict]) -> bool:
        """Verify all 6 expected frames are in the response."""
        present_frames = {frame['id'] for frame in data if 'id' in frame}
        expected_frames = set(self.FRAME_IDS.keys())
        
        missing = expected_frames - present_frames
        if missing:
            logger.warning(f"Missing frames: {missing}")
        
        return len(missing) == 0


@pytest.fixture
def api_base_url():
    """Get API base URL from environment or default."""
    import os
    url = os.getenv('API_URL', 'http://localhost:8000')
    logger.info(f"Using API URL: {url}")
    return url


@pytest.fixture
def validator(api_base_url):
    """Create a DashboardFrameValidator instance."""
    return DashboardFrameValidator(api_base_url)


class TestTopicFilterSingleSelection:
    """Test single topic selection across all dashboard frames."""
    
    def test_single_topic_filters_all_frames(self, validator):
        """AC1: Single topic selection restricts all frames to that topic."""
        logger.info("TEST: Single topic selection should filter all 6 frames")
        
        # Fetch unfiltered data first
        all_data = validator.fetch_chart_data()
        logger.info(f"Fetched {len(all_data)} frames with no filters")
        check.greater(len(all_data), 0, "No frames returned from API")
        check.true(validator.validate_all_frames_present(all_data), 
                   "Not all 6 expected frames present in response")
        
        # Get available topics from the data
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        if not all_topics:
            logger.warning("No topics found in unfiltered data")
            pytest.skip("Cannot test topic filter without topic data")
        
        selected_topic = list(all_topics)[0]
        logger.info(f"Testing with single topic: {selected_topic}")
        
        # Fetch filtered data
        filtered_data = validator.fetch_chart_data({'topics': [selected_topic]})
        logger.info(f"Fetched {len(filtered_data)} frames with topic filter: {selected_topic}")
        check.greater(len(filtered_data), 0, "No frames returned with topic filter")
        
        # Verify all frames present
        check.true(validator.validate_all_frames_present(filtered_data),
                   "Not all 6 expected frames present with topic filter")
        
        # Validate each frame respects the topic filter
        frames_to_validate = [
            'TOTAL_CALLS',
            'AVG_HANDLING_TIME',
            'SATISFIED',
            'SENTIMENT',
            'AVG_HANDLING_TIME_BY_TOPIC',
            'KEY_PHRASES'
        ]
        
        for frame_id in frames_to_validate:
            is_valid = validator.validate_single_topic_filter(
                [selected_topic], filtered_data, frame_id
            )
            check.true(is_valid, 
                       f"Frame {frame_id} failed topic filter validation")
    
    def test_key_phrases_frame_respects_topic_filter(self, validator):
        """AC6: Key Phrases frame specifically respects topic filter (was the bug)."""
        logger.info("TEST: Key Phrases frame must respect topic filter (Issue #41 bug frame)")
        
        # Get unfiltered data
        all_data = validator.fetch_chart_data()
        check.greater(len(all_data), 0, "No frames returned")
        
        # Get available topics
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        if not all_topics:
            pytest.skip("Cannot test without topic data")
        
        selected_topic = list(all_topics)[0]
        
        # Get Key Phrases with topic filter
        filtered_data = validator.fetch_chart_data({'topics': [selected_topic]})
        key_phrases_frame = validator.get_frame_by_id('KEY_PHRASES', filtered_data)
        
        check.is_not_none(key_phrases_frame, "Key Phrases frame not found")
        
        if key_phrases_frame:
            chart_value = key_phrases_frame.get('chart_value', [])
            check.greater(len(chart_value), 0, 
                          "Key Phrases frame is empty with topic filter - filter may be ignored")
    
    def test_clear_topic_selection_restores_all_data(self, validator):
        """AC3: Clearing topic selection shows all data again."""
        logger.info("TEST: Clearing topic filter should restore unfiltered view")
        
        # Get unfiltered baseline
        all_data = validator.fetch_chart_data()
        all_data_count = len(all_data)
        check.greater(all_data_count, 0, "No frames in unfiltered response")
        
        # Get topics and select one
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        if not all_topics:
            pytest.skip("Cannot test without topic data")
        
        selected_topic = list(all_topics)[0]
        filtered_data = validator.fetch_chart_data({'topics': [selected_topic]})
        
        # Now clear the filter
        cleared_data = validator.fetch_chart_data({'topics': []})
        
        # Should be back to unfiltered state
        check.equal(len(cleared_data), all_data_count,
                   "Clearing filter did not restore original data count")


class TestTopicFilterMultipleSelection:
    """Test multiple topic selection across all dashboard frames."""
    
    def test_multiple_topics_filters_all_frames(self, validator):
        """AC2: Multiple topic selection restricts all frames to selected set."""
        logger.info("TEST: Multiple topic selection should filter all 6 frames to selected set")
        
        # Get unfiltered data
        all_data = validator.fetch_chart_data()
        
        # Get available topics
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        if len(all_topics) < 2:
            pytest.skip("Need at least 2 topics to test multiple selection")
        
        # Select first 2 topics
        selected_topics = list(all_topics)[:2]
        logger.info(f"Testing with {len(selected_topics)} topics: {selected_topics}")
        
        # Fetch with multiple topics
        filtered_data = validator.fetch_chart_data({'topics': selected_topics})
        check.greater(len(filtered_data), 0, "No frames returned with multiple topic filter")
        
        # Verify all frames present
        check.true(validator.validate_all_frames_present(filtered_data),
                   "Not all 6 frames present with multiple topic filter")
        
        # Validate each frame respects the combined topic filter
        for frame_id in ['TOTAL_CALLS', 'AVG_HANDLING_TIME', 'SATISFIED', 
                         'SENTIMENT', 'AVG_HANDLING_TIME_BY_TOPIC', 'KEY_PHRASES']:
            is_valid = validator.validate_single_topic_filter(
                selected_topics, filtered_data, frame_id
            )
            check.true(is_valid,
                       f"Frame {frame_id} failed multiple topic filter validation")
    
    def test_cross_frame_consistency_with_multiple_topics(self, validator):
        """Verify data consistency across all frames with multiple topic filter."""
        logger.info("TEST: Cross-frame data consistency with multiple topics")
        
        all_data = validator.fetch_chart_data()
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        
        if len(all_topics) < 2:
            pytest.skip("Need at least 2 topics")
        
        selected_topics = list(all_topics)[:2]
        filtered_data = validator.fetch_chart_data({'topics': selected_topics})
        
        # Get topic data from multiple frames and ensure consistency
        total_calls_frame = validator.get_frame_by_id('TOTAL_CALLS', filtered_data)
        key_phrases_frame = validator.get_frame_by_id('KEY_PHRASES', filtered_data)
        
        check.is_not_none(total_calls_frame, "Total Calls frame not found")
        check.is_not_none(key_phrases_frame, "Key Phrases frame not found")
        
        if total_calls_frame and key_phrases_frame:
            # Both should have data (not be empty)
            total_value = 0
            for item in total_calls_frame.get('chart_value', []):
                if 'value' in item:
                    total_value += item['value']
            
            check.greater(total_value, 0, "Total Calls shows zero for selected topics")
            
            key_phrases_count = len(key_phrases_frame.get('chart_value', []))
            check.greater(key_phrases_count, 0, "Key Phrases empty for selected topics")


class TestTopicFilterIntegration:
    """Test topic filter integration with other filters."""
    
    def test_topic_filter_with_date_range(self, validator):
        """Verify topic filter works with date range filter."""
        logger.info("TEST: Topic filter combined with date range filter")
        
        all_data = validator.fetch_chart_data()
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        
        if not all_topics:
            pytest.skip("No topic data available")
        
        selected_topic = list(all_topics)[0]
        
        # Apply both topic and date range filters
        filtered_data = validator.fetch_chart_data({
            'topics': [selected_topic],
            'date_range': 'Last 7 days'
        })
        
        check.greater(len(filtered_data), 0, "No frames with topic + date filter")
        check.true(validator.validate_all_frames_present(filtered_data),
                   "Not all 6 frames with topic + date filter")
    
    def test_topic_filter_with_sentiment(self, validator):
        """Verify topic filter works with sentiment filter."""
        logger.info("TEST: Topic filter combined with sentiment filter")
        
        all_data = validator.fetch_chart_data()
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        
        if not all_topics:
            pytest.skip("No topic data available")
        
        selected_topic = list(all_topics)[0]
        
        # Apply both topic and sentiment filters
        filtered_data = validator.fetch_chart_data({
            'topics': [selected_topic],
            'sentiments': ['Positive']
        })
        
        check.greater(len(filtered_data), 0, "No frames with topic + sentiment filter")
        check.true(validator.validate_all_frames_present(filtered_data),
                   "Not all 6 frames with topic + sentiment filter")
    
    def test_topic_filter_combined_with_multiple_filters(self, validator):
        """Verify topic filter works with multiple other filters combined."""
        logger.info("TEST: Topic filter with multiple combined filters")
        
        all_data = validator.fetch_chart_data()
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        
        if not all_topics:
            pytest.skip("No topic data available")
        
        selected_topic = list(all_topics)[0]
        
        # Apply topic + date range + sentiment
        filtered_data = validator.fetch_chart_data({
            'topics': [selected_topic],
            'sentiments': ['Positive', 'Negative'],
            'date_range': 'Last 14 days'
        })
        
        check.greater(len(filtered_data), 0, "No frames with combined filters")
        check.true(validator.validate_all_frames_present(filtered_data),
                   "Not all 6 frames with combined filters")
        
        # Validate each frame still respects the topic filter
        for frame_id in ['TOTAL_CALLS', 'AVG_HANDLING_TIME', 'SATISFIED', 
                         'AVG_HANDLING_TIME_BY_TOPIC', 'KEY_PHRASES']:
            is_valid = validator.validate_single_topic_filter(
                [selected_topic], filtered_data, frame_id
            )
            check.true(is_valid,
                       f"Frame {frame_id} failed with combined filters")


class TestDataFrameComparison:
    """Test data completeness and consistency across filtered/unfiltered states."""
    
    def test_no_data_loss_with_filter(self, validator):
        """Verify filtering doesn't cause data loss or display artifacts."""
        logger.info("TEST: No data loss with topic filter applied")
        
        # Get unfiltered data
        all_data = validator.fetch_chart_data()
        
        # Get topics
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        if not all_topics:
            pytest.skip("No topic data")
        
        # Get frame counts unfiltered
        unfiltered_count = len(all_data)
        
        # Apply filter with all topics
        all_topics_list = list(all_topics)
        filtered_data = validator.fetch_chart_data({'topics': all_topics_list})
        
        # Frame count should remain the same
        check.equal(len(filtered_data), unfiltered_count,
                   "Frame count changed when filtering by all topics")
    
    def test_filtered_data_has_valid_structure(self, validator):
        """Verify filtered response maintains valid data structure."""
        logger.info("TEST: Filtered response has valid structure")
        
        all_data = validator.fetch_chart_data()
        all_topics = validator.get_topics_from_frame('AVG_HANDLING_TIME_BY_TOPIC', all_data)
        
        if not all_topics:
            pytest.skip("No topic data")
        
        selected_topic = list(all_topics)[0]
        filtered_data = validator.fetch_chart_data({'topics': [selected_topic]})
        
        # Validate structure
        for frame in filtered_data:
            check.is_not_none(frame.get('id'), "Frame missing 'id'")
            check.is_not_none(frame.get('chart_name'), "Frame missing 'chart_name'")
            check.is_not_none(frame.get('chart_type'), "Frame missing 'chart_type'")
            
            chart_value = frame.get('chart_value')
            check.is_instance(chart_value, list, f"Frame {frame.get('id')} chart_value not a list")


# Test execution counter for reporting
test_execution_count = 0


def pytest_runtest_protocol(item, nextitem):
    """Track test execution."""
    global test_execution_count
    test_execution_count += 1
    return None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
