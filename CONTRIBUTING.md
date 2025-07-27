# Contributing to DevOps Playbook

First off, thank you for considering contributing to the DevOps Playbook! It's people like you that make this resource valuable for the DevOps community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- A clear and descriptive title
- Steps to reproduce the issue
- Expected vs actual behavior
- System information (OS, Python version, etc.)
- Relevant logs or error messages

### 💡 Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:

- A clear description of the enhancement
- Use cases and benefits
- Possible implementation approach
- Any potential drawbacks

### 📝 Improving Documentation

- Fix typos or clarify confusing sections
- Add examples or diagrams
- Translate documentation to other languages
- Add new sections for uncovered topics

### 🔧 Contributing Code

Areas where we especially need help:

1. **DORA Metrics Scripts**
   - Support for additional CI/CD platforms
   - Performance optimizations
   - Additional output formats
   - Better error handling

2. **New Content**
   - Real-world case studies
   - Tool comparisons
   - Best practices guides
   - Troubleshooting guides

3. **Infrastructure Templates**
   - Terraform modules
   - Ansible playbooks
   - Kubernetes manifests
   - Helm charts

## Getting Started

1. **Fork the Repository**
   ```bash
   git clone https://github.com/jefrnc/devops-playbook.git
   cd devops-playbook
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set Up Development Environment**
   ```bash
   # For Python scripts
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

4. **Make Your Changes**
   - Write code
   - Add tests
   - Update documentation

5. **Test Your Changes**
   ```bash
   # Run tests
   pytest tests/
   
   # Check code style
   flake8 scripts/
   
   # Check documentation
   markdownlint '**/*.md'
   ```

## Pull Request Process

1. **Ensure Quality**
   - [ ] Code follows the style guidelines
   - [ ] Tests pass locally
   - [ ] Documentation is updated
   - [ ] Commit messages are clear

2. **Submit PR**
   - Use a clear PR title
   - Reference any related issues
   - Describe what changes you made and why
   - Include screenshots for UI changes

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Performance improvement
   
   ## Testing
   - [ ] Tests pass locally
   - [ ] New tests added (if applicable)
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   ```

## Style Guidelines

### Python Code Style

We follow PEP 8 with these additions:

```python
# Good: Descriptive variable names
deployment_frequency = calculate_deployment_frequency(start_date, end_date)

# Good: Type hints
def calculate_mttr(incidents: List[Incident]) -> float:
    """Calculate Mean Time to Recovery."""
    pass

# Good: Comprehensive docstrings
def process_deployment(deployment_id: str) -> DeploymentResult:
    """
    Process a deployment and return its result.
    
    Args:
        deployment_id: Unique identifier for the deployment
        
    Returns:
        DeploymentResult object containing status and metrics
        
    Raises:
        DeploymentError: If deployment processing fails
    """
    pass
```

### Documentation Style

- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Follow this structure:
  ```markdown
  # Feature Name
  
  ## Overview
  Brief description
  
  ## Prerequisites
  What's needed
  
  ## Usage
  How to use it
  
  ## Examples
  Real examples
  
  ## Troubleshooting
  Common issues
  ```

### Commit Messages

Follow the conventional commits specification:

```
feat: add support for GitLab CI in deployment frequency calculator
fix: correct timezone handling in MTTR calculations
docs: add troubleshooting guide for AWS authentication
chore: update dependencies to latest versions
```

## Testing

### Python Scripts

```python
# tests/test_deployment_frequency.py
def test_calculate_deployment_frequency():
    """Test deployment frequency calculation."""
    deployments = [
        {'timestamp': '2024-01-01T10:00:00Z', 'status': 'success'},
        {'timestamp': '2024-01-02T10:00:00Z', 'status': 'success'},
    ]
    
    result = calculate_deployment_frequency(deployments)
    assert result['daily_average'] == 2.0
    assert result['performance_level'] == 'Elite'
```

### Documentation

- Ensure all links work
- Verify code examples run
- Check for spelling/grammar

## Community

### Getting Help

- 💬 [GitHub Discussions](https://github.com/jefrnc/devops-playbook/discussions) - Ask questions
- 🐛 [Issues](https://github.com/jefrnc/devops-playbook/issues) - Report bugs
- 💡 [Ideas](https://github.com/jefrnc/devops-playbook/discussions/categories/ideas) - Share ideas

### Recognition

Contributors will be:
- Listed in our [Contributors](CONTRIBUTORS.md) file
- Mentioned in release notes
- Given credit in relevant documentation

## Development Setup

### Required Tools

- Python 3.8+
- Git
- Docker (for testing)
- Make (optional)

### Makefile Commands

```makefile
make install    # Install dependencies
make test       # Run tests
make lint       # Check code style
make docs       # Build documentation
make all        # Run everything
```

## Release Process

1. Update version numbers
2. Update CHANGELOG.md
3. Create release PR
4. Tag release after merge
5. Publish release notes

## Questions?

Feel free to:
- Open an issue for clarification
- Start a discussion
- Contact maintainers

Thank you for contributing to make DevOps better for everyone! 🚀
