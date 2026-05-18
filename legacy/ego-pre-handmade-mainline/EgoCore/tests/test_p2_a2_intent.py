"""
Tests for P2-A.2: Intent Mapping and Postcondition Validation

These tests verify that:
1. IntentMapper correctly parses user requests
2. PostconditionValidator detects path mismatches
3. "Fake completed" scenarios are prevented
"""

import os
import tempfile
import shutil
import pytest

from app.runtime.intent_mapper import (
    IntentMapper, OperationIntent, OperationType, parse_intent
)
from app.runtime.postcondition import (
    PostconditionValidator, PostconditionResult, validate_postcondition
)
from app.runtime.execution_result import (
    UnifiedExecutionResult, FailureClass, ExecutionEvidence
)


class TestIntentMapper:
    """Tests for IntentMapper class."""
    
    def setup_method(self):
        """Create a fresh mapper for each test."""
        self.mapper = IntentMapper()
    
    def test_list_dir_with_path(self):
        """Test parsing '看看 X 里有哪些文件'."""
        intent = self.mapper.parse('帮我看看/home/moonlight/docs里有哪些文件')
        
        assert intent.operation == OperationType.LIST_DIR
        assert intent.target_path == '/home/moonlight/docs'
        assert intent.confidence > 0.5
    
    def test_list_dir_with_trailing_slash(self):
        """Test that trailing slash is handled correctly."""
        intent = self.mapper.parse('帮我看看/home/moonlight/docs/里有哪些文件')
        
        assert intent.operation == OperationType.LIST_DIR
        assert intent.target_path == '/home/moonlight/docs'
    
    def test_write_file_in_directory(self):
        """Test parsing '在 X 里创建 Y 文件'."""
        intent = self.mapper.parse('帮我在/home/Test/里创建一个test.md文件')
        
        assert intent.operation == OperationType.WRITE_FILE
        assert intent.target_path == '/home/Test/test.md'
        assert intent.target_name == 'test.md'
    
    def test_read_file(self):
        """Test parsing '读取 X 文件'."""
        intent = self.mapper.parse('读取 /home/user/test.py 文件')
        
        assert intent.operation == OperationType.READ_FILE
        assert intent.target_path == '/home/user/test.py'
    
    def test_mkdir(self):
        """Test parsing '创建 X 目录'."""
        intent = self.mapper.parse('创建 /home/user/newdir 目录')
        
        assert intent.operation == OperationType.MKDIR
        assert intent.target_path == '/home/user/newdir'
    
    def test_exists(self):
        """Test parsing '检查 X 是否存在'."""
        intent = self.mapper.parse('检查 /home/user/test 是否存在')
        
        assert intent.operation == OperationType.EXISTS
        assert intent.target_path == '/home/user/test'
    
    def test_unknown_operation(self):
        """Test that unknown operations return UNKNOWN."""
        intent = self.mapper.parse('这是一句无关的话')
        
        assert intent.operation == OperationType.UNKNOWN
    
    def test_write_file_various_extensions(self):
        """Test file creation with various extensions."""
        test_cases = [
            ('在/tmp里创建config.json文件', '/tmp/config.json', 'config.json'),
            ('在/data下创建readme.txt文件', '/data/readme.txt', 'readme.txt'),
            ('创建notes.md文件', 'notes.md', None),  # No directory specified
        ]
        
        for text, expected_path, expected_name in test_cases:
            intent = self.mapper.parse(text)
            assert intent.operation == OperationType.WRITE_FILE, f"Failed for: {text}"
            assert intent.target_path == expected_path, f"Path mismatch for: {text}"


class TestPostconditionValidator:
    """Tests for PostconditionValidator class."""
    
    def setup_method(self):
        """Create a fresh validator for each test."""
        self.validator = PostconditionValidator()
    
    def test_path_match_validation(self):
        """Test that matching paths pass validation."""
        intent = OperationIntent(
            operation=OperationType.LIST_DIR,
            target_path='/home/user/docs',
            raw_text='test'
        )
        
        result = self.validator.validate(intent, '/home/user/docs')
        
        assert result.success
        assert result.path_match
    
    def test_path_mismatch_detection(self):
        """Test that mismatched paths fail validation."""
        intent = OperationIntent(
            operation=OperationType.LIST_DIR,
            target_path='/home/user/docs',
            raw_text='test'
        )
        
        result = self.validator.validate(intent, '/home/user')
        
        assert not result.success
        assert not result.path_match
        assert result.to_failure_class() == FailureClass.INTENT_MISMATCH
    
    def test_write_file_existence_check(self):
        """Test that write operations verify file existence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.txt')
            
            intent = OperationIntent(
                operation=OperationType.WRITE_FILE,
                target_path=test_file,
                raw_text='test'
            )
            
            # File doesn't exist yet
            result = self.validator.validate(intent, test_file)
            assert not result.exists_check
            
            # Create file
            with open(test_file, 'w') as f:
                f.write('test')
            
            # Now should pass
            result = self.validator.validate(intent, test_file)
            assert result.exists_check
    
    def test_validate_and_wrap_result_success(self):
        """Test that successful results pass through."""
        intent = OperationIntent(
            operation=OperationType.LIST_DIR,
            target_path='/home/user/docs',
            raw_text='test'
        )
        
        tool_result = UnifiedExecutionResult.success_result(
            summary='List success',
            output='file1, file2'
        )
        
        validated = self.validator.validate_and_wrap_result(
            intent, '/home/user/docs', tool_result
        )
        
        assert validated.success
    
    def test_validate_and_wrap_result_mismatch(self):
        """Test that mismatched paths convert success to failure."""
        intent = OperationIntent(
            operation=OperationType.LIST_DIR,
            target_path='/home/user/docs',
            raw_text='test'
        )
        
        tool_result = UnifiedExecutionResult.success_result(
            summary='List success',
            output='file1, file2'
        )
        
        validated = self.validator.validate_and_wrap_result(
            intent, '/home/user', tool_result  # Wrong path!
        )
        
        assert not validated.success
        assert validated.failure_class == FailureClass.INTENT_MISMATCH


class TestIntegration:
    """Integration tests for the full P2-A.2 flow."""
    
    def test_full_flow_list_dir_correct(self):
        """Test complete flow: parse intent -> execute -> validate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            docs_dir = os.path.join(tmpdir, 'docs')
            os.makedirs(docs_dir)
            with open(os.path.join(docs_dir, 'file1.md'), 'w') as f:
                f.write('# Test')
            
            # Parse intent
            intent = parse_intent(f'帮我看看{docs_dir}里有哪些文件')
            
            assert intent.operation == OperationType.LIST_DIR
            assert intent.target_path == docs_dir
            
            # Execute (simulated)
            items = os.listdir(docs_dir)
            
            # Validate
            validator = PostconditionValidator()
            tool_result = UnifiedExecutionResult.success_result(
                summary='List success',
                output=', '.join(items)
            )
            
            validated = validator.validate_and_wrap_result(intent, docs_dir, tool_result)
            
            assert validated.success
    
    def test_full_flow_detect_wrong_path(self):
        """Test that wrong path is detected even if tool succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            docs_dir = os.path.join(tmpdir, 'docs')
            os.makedirs(docs_dir)
            
            # Parse intent asking for docs
            intent = parse_intent(f'帮我看看{docs_dir}里有哪些文件')
            
            # But accidentally list parent directory
            items = os.listdir(tmpdir)  # Wrong directory!
            
            # Validate
            validator = PostconditionValidator()
            tool_result = UnifiedExecutionResult.success_result(
                summary='List success',
                output=', '.join(items)
            )
            
            validated = validator.validate_and_wrap_result(intent, tmpdir, tool_result)
            
            # Should fail because path doesn't match intent
            assert not validated.success
            assert validated.failure_class == FailureClass.INTENT_MISMATCH


class TestFailureClasses:
    """Tests for new failure classes."""
    
    def test_intent_mismatch_exists(self):
        """Test that INTENT_MISMATCH failure class exists."""
        assert FailureClass.INTENT_MISMATCH.value == 'intent_mismatch'
    
    def test_postcondition_failed_exists(self):
        """Test that POSTCONDITION_FAILED failure class exists."""
        assert FailureClass.POSTCONDITION_FAILED.value == 'postcondition_failed'
    
    def test_path_extraction_error_exists(self):
        """Test that PATH_EXTRACTION_ERROR failure class exists."""
        assert FailureClass.PATH_EXTRACTION_ERROR.value == 'path_extraction_error'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
