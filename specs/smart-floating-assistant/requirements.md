# Requirements Document

## Introduction

The Smart Floating Assistant Addon is a PySide6-based floating assistant that uses the GGUF Loader application as a backend for model loading only. The addon operates independently with its own floating interface that detects selected text globally across any application, displays a contextual floating button wherever text is selected, and allows users to generate summaries or comments using the GGUF model loaded by the backend. The addon automatically starts when GGUF Loader opens and provides a seamless workflow for text enhancement and analysis without interfering with the main application's interface.

## Requirements

### Requirement 1

**User Story:** As a user working in any application, I want the system to detect when I select text, so that I can access AI-powered text processing without switching applications.

#### Acceptance Criteria

1. WHEN text is selected in any application THEN the system SHALL detect the selection globally
2. WHEN text is clicked or highlighted THEN the system SHALL capture the selected text content
3. WHEN no text is selected THEN the system SHALL not trigger any floating UI elements
4. WHEN text selection changes THEN the system SHALL update the captured text accordingly

### Requirement 2

**User Story:** As a user who has selected text, I want to see a floating button near my cursor, so that I can easily access text processing options without disrupting my workflow.

#### Acceptance Criteria

1. WHEN text is selected THEN the system SHALL display a transparent floating button near the mouse cursor
2. WHEN the floating button is displayed THEN it SHALL be positioned within 50 pixels of the cursor location
3. WHEN the user moves the cursor away from the selected text THEN the floating button SHALL remain visible for at least 3 seconds
4. WHEN no text is selected for more than 5 seconds THEN the floating button SHALL automatically hide
5. WHEN the floating button is clicked THEN it SHALL open the text processing popup window

### Requirement 3

**User Story:** As a user who clicked the floating button, I want to see a popup window with my selected text automatically copied and processing options available, so that I can choose how to enhance the selected text.

#### Acceptance Criteria

1. WHEN the floating button is clicked THEN the system SHALL open a PySide6 popup window
2. WHEN the popup window opens THEN it SHALL automatically display the selected text in a text area
3. WHEN the popup window is displayed THEN it SHALL show two action buttons: "Summarize" and "Comment"
4. WHEN the popup window is open THEN it SHALL remain on top of other windows
5. WHEN the user clicks outside the popup window THEN it SHALL close automatically
6. WHEN the popup window displays text THEN it SHALL handle text of any length in a scrollable text area

### Requirement 4

**User Story:** As a user who wants to process selected text, I want to generate summaries or comments using AI only when I explicitly request it, so that I have full control over when AI processing occurs.

#### Acceptance Criteria

1. WHEN the popup window is displayed THEN the system SHALL NOT automatically process any text
2. WHEN the "Summarize" button is clicked THEN the system SHALL process the text with the prompt "Summarize this clearly: {text}"
3. WHEN the "Comment" button is clicked THEN the system SHALL process the text with the prompt "Write a friendly and insightful comment about: {text}"
4. WHEN text processing begins THEN the system SHALL show a loading indicator in the popup window
5. WHEN summarization is complete THEN the system SHALL display the summary result in the addon screen
6. WHEN comment generation is complete THEN the system SHALL display the comment result in the addon screen AND show a "Paste Comment" button
7. WHEN text processing fails THEN the system SHALL display an error message to the user
8. WHEN neither "Summarize" nor "Comment" buttons have been clicked THEN the system SHALL perform no AI processing

### Requirement 5

**User Story:** As a user who has generated a comment, I want to paste it wherever I place my cursor, so that I can seamlessly integrate the AI-generated comment into my work.

#### Acceptance Criteria

1. WHEN a comment is generated THEN the system SHALL display a "Paste Comment" button
2. WHEN the "Paste Comment" button is clicked THEN the system SHALL insert the generated comment at the current cursor location
3. WHEN inserting text THEN the system SHALL use either pyautogui.write() or system-level keystroke injection
4. WHEN text insertion is successful THEN the system SHALL provide visual feedback to the user
5. WHEN no input field is focused THEN the system SHALL copy the generated comment to clipboard and show a notification
6. WHEN text insertion fails THEN the system SHALL display an error message and offer to copy to clipboard
7. WHEN a summary is generated THEN no paste button SHALL be shown (summaries are for reading only)

### Requirement 6

**User Story:** As a user of the GGUF Loader application, I want the floating assistant to use the GGUF Loader only as a backend for model loading while maintaining its own independent interface, so that I can access AI capabilities anywhere without disrupting the main application.

#### Acceptance Criteria

1. WHEN the GGUF Loader application starts THEN the addon SHALL automatically start and run in the background
2. WHEN the addon needs to process text THEN it SHALL use the GGUF model loaded by the GGUF Loader backend
3. WHEN the GGUF model is not available in the backend THEN the addon SHALL display an appropriate error message
4. WHEN the addon operates THEN it SHALL maintain its own independent floating interface separate from the main GGUF Loader UI
5. WHEN the addon is installed THEN it SHALL be located in the `addons/smart_floater/` directory
6. WHEN text is selected anywhere on the screen THEN the addon's floating interface SHALL appear regardless of which application is active

### Requirement 7

**User Story:** As a user concerned about privacy, I want all text processing to happen locally and offline, so that my sensitive information never leaves my device.

#### Acceptance Criteria

1. WHEN text is processed THEN the system SHALL use only locally loaded GGUF models
2. WHEN the addon operates THEN it SHALL not make any network requests for text processing
3. WHEN text is captured or processed THEN it SHALL remain on the local device only
4. WHEN the addon is running THEN it SHALL not transmit any user data to external services

### Requirement 8

**User Story:** As a developer maintaining the system, I want the addon to be modular and well-structured, so that it can be easily maintained and extended.

#### Acceptance Criteria

1. WHEN the addon is implemented THEN it SHALL be split into separate modules: main.py, floater_ui.py, comment_engine.py, and injector.py
2. WHEN the addon initializes THEN main.py SHALL handle hooks and launch the assistant
3. WHEN UI elements are needed THEN floater_ui.py SHALL handle the floating button and popup interface
4. WHEN text processing is required THEN comment_engine.py SHALL handle summarization and comment generation
5. WHEN text insertion is needed THEN injector.py SHALL handle pasting into input fields