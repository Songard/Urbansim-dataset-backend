# Claude Code Development Guidelines

## Code Cleanup and Maintenance

### Always Clean Up After Development
- Remove all test files, example files, and debugging scripts after completing features
- Delete any temporary files or directories created during development
- Remove unused imports and dead code
- Clean up any hardcoded paths or test data

### Files to Always Clean Up
- `test_*.py` - Test scripts
- `example_*.py` - Example usage scripts  
- `demo_*.py` - Demo scripts
- `debug_*.py` - Debug utilities
- `verify_*.py` - Verification scripts
- Any files with hardcoded local paths
- Temporary visualization or analysis tools

### Project Maintenance Checklist

#### Before Completing Any Task:
1. **Remove test/example files** created during development
2. **Update .gitignore** with new file types or directories if needed
3. **Update requirements.txt** with any new dependencies
4. **Update README.md** or relevant documentation with changes
5. **Remove any emoji** from code comments or strings
6. **Check for hardcoded paths** and replace with config variables
7. **Remove debugging print statements** and console.log equivalents

#### Documentation Updates:
- Update README.md for major feature changes
- Update docstrings for modified functions
- Create or update documentation in relevant subdirectories
- Document new configuration options in config.py
- Update API documentation if applicable

#### Code Quality:
- No emoji in code, comments, or strings
- Use proper logging instead of print statements for production code
- Follow existing code style and naming conventions
- Remove commented-out code blocks
- Ensure all functions have proper docstrings

### Git Best Practices
- Commit only production-ready code
- Never commit test files or examples to main branch
- Use meaningful commit messages
- Stage changes carefully to avoid including temp files

### Configuration Management
- Add new settings to config.py instead of hardcoding
- Update environment variable documentation
- Ensure sensitive data uses environment variables
- Document all configuration options

### Dependencies
- Update requirements.txt immediately when adding new packages
- Remove unused dependencies
- Pin version numbers for stability
- Document any system-level dependencies

## Commands to Run Before Finishing

```bash
# Clean up Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Check for test files
find . -name "test_*.py" -o -name "example_*.py" -o -name "demo_*.py"

# Update requirements
pip freeze > requirements.txt

# Check git status
git status
git diff
```

## Remember
- Keep the codebase clean and production-ready
- Document all changes appropriately  
- Test functionality before considering work complete
- Remove all development artifacts before finishing