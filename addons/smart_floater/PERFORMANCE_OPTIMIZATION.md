# Performance Optimization and Edge Case Handling

This document describes the performance optimization features and edge case handling implemented for the Smart Floating Assistant addon.

## Overview

The performance optimization system provides:

1. **Text Length Limits** - Enforces 10,000 character limit with user warnings
2. **Memory Management** - Prevents memory leaks through proper widget cleanup
3. **UI Responsiveness** - Maintains responsive UI during AI processing
4. **Special Character Handling** - Sanitizes text and handles encoding issues
5. **Performance Monitoring** - Tracks system performance and resource usage

## Components

### TextValidator

Handles text validation, sanitization, and length limits.

**Features:**
- Maximum text length: 10,000 characters
- Maximum lines: 500
- Maximum line length: 1,000 characters
- Unicode normalization (NFKC)
- Special character removal/replacement
- Whitespace cleanup
- Text complexity analysis

**Usage:**
```python
from addons.smart_floater.performance_optimizer import TextValidator

validator = TextValidator()
result = validator.validate_and_sanitize(text)

if result.is_valid:
    processed_text = result.sanitized_text
    # Show warnings if any
    for warning in result.warnings:
        print(f"Warning: {warning}")
else:
    # Handle errors
    for error in result.errors:
        print(f"Error: {error}")
```

### MemoryManager

Manages memory usage and prevents memory leaks.

**Features:**
- Object tracking for cleanup
- Memory usage monitoring
- Automatic cleanup when threshold exceeded
- Garbage collection optimization
- Memory threshold alerts (default: 100MB)

**Usage:**
```python
from addons.smart_floater.performance_optimizer import MemoryManager

memory_manager = MemoryManager()

# Track objects for cleanup
memory_manager.track_object(widget, widget.deleteLater)

# Check memory usage
current_usage = memory_manager.get_memory_usage()

# Force cleanup if needed
if memory_manager.check_memory_threshold():
    memory_manager.force_cleanup()
```

### UIResponsivenessOptimizer

Optimizes UI responsiveness during processing operations.

**Features:**
- Asynchronous processing using QThread
- Mutex-based concurrency control
- Processing cancellation support
- Thread lifecycle management

**Usage:**
```python
from addons.smart_floater.performance_optimizer import UIResponsivenessOptimizer

ui_optimizer = UIResponsivenessOptimizer()

# Process function asynchronously
def processing_function(text):
    # Heavy processing here
    return processed_result

thread = ui_optimizer.process_async(processing_function, text)
if thread:
    thread.result_ready.connect(handle_result)
    thread.error_occurred.connect(handle_error)
```

### PerformanceMonitor

Monitors system performance and provides metrics.

**Features:**
- Real-time performance metrics collection
- Memory usage tracking
- Widget count monitoring
- Thread count monitoring
- Performance warnings
- Historical data storage

**Metrics Collected:**
- Memory usage (MB)
- Processing time (ms)
- UI response time (ms)
- Text length
- Widget count
- Thread count
- Timestamp

**Usage:**
```python
from addons.smart_floater.performance_optimizer import PerformanceMonitor

monitor = PerformanceMonitor()
monitor.start_monitoring(interval_ms=5000)

# Connect to signals
monitor.performance_warning.connect(handle_warning)
monitor.memory_threshold_exceeded.connect(handle_memory_issue)

# Get current metrics
current_metrics = monitor.get_current_metrics()
summary = monitor.get_performance_summary()
```

### PerformanceOptimizer

Main coordinator for all performance optimization features.

**Features:**
- Integrates all optimization components
- Provides unified interface
- Handles optimization workflows
- Manages component lifecycle

**Usage:**
```python
from addons.smart_floater.performance_optimizer import PerformanceOptimizer

optimizer = PerformanceOptimizer()
optimizer.start_optimization()

# Validate text before processing
validation_result = optimizer.validate_text_for_processing(text)

# Optimize processing for responsiveness
thread = optimizer.optimize_processing(processing_func, text)

# Get optimization status
status = optimizer.get_optimization_status()

# Cleanup when done
optimizer.cleanup()
```

## Integration with Existing Components

### CommentEngine Integration

The CommentEngine now uses performance optimization for:
- Text validation before processing
- Memory management for processing results
- Performance monitoring during AI operations

### TextInjector Integration

The TextInjector uses optimization for:
- Text validation before injection
- Performance monitoring during injection
- Memory cleanup after operations

### FloaterUI Integration

The FloaterUI components use optimization for:
- Text validation in popup windows
- Widget memory management
- Performance monitoring for UI operations

### Main Controller Integration

The main addon controller integrates optimization through:
- Performance optimizer initialization
- Component lifecycle management
- Performance warning handling

## Text Length Limits and Warnings

### Limits Enforced

- **Maximum text length**: 10,000 characters
- **Maximum lines**: 500 lines
- **Maximum line length**: 1,000 characters per line

### Warning Messages

Users receive warnings for:
- Text approaching length limits
- Many lines detected (performance impact)
- Very long lines detected
- Special characters removed during sanitization
- Unicode normalization applied

### Error Messages

Users receive errors for:
- Text exceeding maximum length
- Empty or invalid text
- Text processing blocked for security reasons

## Special Character Handling

### Characters Handled

1. **Control Characters**: Removed except common whitespace (\n, \r, \t, space)
2. **Zero-width Characters**: Removed (U+200B, U+200C, U+200D, U+FEFF)
3. **Unicode Normalization**: Applied NFKC normalization
4. **Whitespace Cleanup**: Multiple spaces reduced to single space
5. **Line Cleanup**: Excessive empty lines reduced

### Sanitization Process

1. Unicode normalization (NFKC)
2. Control character removal
3. Zero-width character removal
4. Whitespace cleanup
5. Line limit enforcement

## Memory Leak Prevention

### Widget Cleanup

- Automatic widget tracking
- Proper widget disposal (close() and deleteLater())
- Memory usage monitoring
- Cleanup callbacks for custom resources

### Resource Management

- Timer cleanup
- Thread cleanup
- Signal disconnection
- Large data structure clearing

### Memory Monitoring

- Real-time memory usage tracking
- Threshold-based cleanup triggers
- Garbage collection optimization
- Memory leak detection

## UI Responsiveness Optimization

### Asynchronous Processing

- AI processing moved to background threads
- UI remains responsive during processing
- Progress indicators for long operations
- Cancellation support for user control

### Thread Management

- Mutex-based concurrency control
- Proper thread lifecycle management
- Thread cleanup and disposal
- Error handling in worker threads

### Performance Monitoring

- UI response time tracking
- Processing time measurement
- Thread count monitoring
- Performance warning system

## Performance Testing

### Test Coverage

The performance optimization includes comprehensive tests for:

1. **Text Validation Tests**
   - Empty text handling
   - Length limit enforcement
   - Special character sanitization
   - Unicode normalization
   - Whitespace cleanup

2. **Memory Management Tests**
   - Object tracking
   - Cleanup functionality
   - Memory usage measurement
   - Threshold checking

3. **UI Responsiveness Tests**
   - Asynchronous processing
   - Concurrency control
   - Thread cleanup
   - Cancellation support

4. **Performance Monitoring Tests**
   - Metrics collection
   - Warning generation
   - Historical data management
   - Summary reporting

5. **Integration Tests**
   - Component integration
   - End-to-end workflows
   - Memory leak detection
   - Performance under load

### Running Tests

```bash
# Run all performance tests
python -m pytest addons/smart_floater/test_performance.py -v

# Run integration tests
python -m pytest addons/smart_floater/test_performance_integration.py -v

# Run specific test categories
python -m pytest addons/smart_floater/test_performance.py::TestTextValidator -v
python -m pytest addons/smart_floater/test_performance.py::TestMemoryManager -v
```

## Configuration

### Default Settings

```python
# Text validation limits
MAX_TEXT_LENGTH = 10000
MAX_LINE_LENGTH = 1000
MAX_LINES = 500

# Memory management
MEMORY_THRESHOLD_MB = 100

# Performance monitoring
MONITORING_INTERVAL_MS = 5000
METRICS_HISTORY_SIZE = 100

# UI responsiveness
PROCESSING_TIMEOUT_MS = 30000
MAX_RETRY_ATTEMPTS = 3
```

### Customization

Settings can be customized by modifying the respective classes:

```python
# Customize text validator limits
validator = TextValidator()
validator.MAX_TEXT_LENGTH = 5000  # Reduce limit

# Customize memory threshold
memory_manager = MemoryManager()
memory_manager._memory_threshold_mb = 50  # Lower threshold

# Customize monitoring interval
monitor = PerformanceMonitor()
monitor.start_monitoring(interval_ms=1000)  # More frequent monitoring
```

## Best Practices

### For Developers

1. **Always validate text** before processing
2. **Track widgets** for memory management
3. **Use async processing** for heavy operations
4. **Monitor performance** in production
5. **Handle edge cases** gracefully

### For Users

1. **Keep text under 10,000 characters** for best performance
2. **Close popup windows** when not needed
3. **Restart application** if performance degrades
4. **Report performance issues** with specific text examples

## Troubleshooting

### Common Issues

1. **Text too long error**
   - Solution: Reduce text length or split into smaller chunks

2. **High memory usage warning**
   - Solution: Close unused windows, restart application

3. **UI becomes unresponsive**
   - Solution: Cancel current operation, reduce text complexity

4. **Special characters not displaying correctly**
   - Solution: Text is automatically sanitized, this is expected behavior

### Performance Optimization Tips

1. **Process shorter text segments** for faster response
2. **Close popup windows** when finished
3. **Avoid very long lines** in text
4. **Monitor memory usage** during extended use
5. **Restart application** periodically for optimal performance

## Future Enhancements

Planned improvements include:

1. **Adaptive text limits** based on system resources
2. **Advanced memory profiling** and leak detection
3. **Performance analytics** and reporting
4. **User-configurable limits** through settings UI
5. **Background processing optimization** for better responsiveness