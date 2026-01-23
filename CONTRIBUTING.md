# Contributing to GGUF Loader

First off, **thank you so much** for considering contributing to GGUF Loader! Your help makes this project better for everyone, and we’re excited to have you on board. 💙

---

## How Can You Contribute?

There are many ways to contribute, no matter your skill level:

- 🐞 **Report bugs or issues** you find  
- 💡 **Suggest new features or improvements**  
- 🛠️ **Fix bugs or add new features** through pull requests  
- 📚 **Improve documentation** or write tutorials  
- 🗣️ **Help answer questions** in discussions or issues  

---

## Getting Started

1. **Fork the repository**  
2. **Clone your fork locally**  
3. Create a new branch for your work:  
   ```bash
   git checkout -b my-feature

```

### 4. Make Your Changes

- Write clean, readable code
- Follow existing code style
- Add comments where needed
- Test your changes thoroughly

### 5. Commit Your Changes

```bash
git add .
git commit -m "Add: brief description of your changes"
```

Use clear commit messages:
- `Add: new feature description`
- `Fix: bug description`
- `Update: what was updated`
- `Docs: documentation changes`

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title describing the change
- Description of what and why
- Any relevant issue numbers

## Code Guidelines

### Python Style

- Follow PEP 8 style guide
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### Example:

```python
def process_text(text: str, max_length: int = 100) -> str:
    """
    Process and truncate text to specified length.
    
    Args:
        text: Input text to process
        max_length: Maximum length of output
        
    Returns:
        Processed text string
    """
    return text[:max_length]
```

## Reporting Bugs

### Before Reporting

- Check if the bug is already reported
- Try the latest version
- Gather relevant information

### Bug Report Should Include

- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version)
- Error messages and logs
- Screenshots if applicable

## Suggesting Features

### Good Feature Requests Include

- Clear description of the feature
- Use case and benefits
- Possible implementation approach
- Examples or mockups if applicable

## Documentation

Help improve our docs:

- Fix typos and grammar
- Add examples and tutorials
- Clarify confusing sections
- Translate to other languages

Documentation files are in the `docs/` folder.

## Testing

Before submitting:

- Test your changes thoroughly
- Ensure existing features still work
- Test on different platforms if possible
- Add tests for new features

## Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Ensure all tests pass**
4. **Update CHANGELOG** if applicable
5. **Request review** from maintainers

### PR Review Process

- Maintainers will review your PR
- Address any requested changes
- Once approved, it will be merged
- Your contribution will be credited!

## Community Guidelines

- Be respectful and inclusive
- Help others learn and grow
- Give constructive feedback
- Follow our [Code of Conduct](CODE_OF_CONDUCT.MD)

## Questions?

- 💬 [GitHub Discussions](https://github.com/GGUFloader/gguf-loader/discussions)
- 🐛 [GitHub Issues](https://github.com/GGUFloader/gguf-loader/issues)
- 📧 Email: hossainnazary475@gmail.com

## Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing to GGUF Loader! 🎉
