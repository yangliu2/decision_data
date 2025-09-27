# Atlassian API Integration Guide

## Overview

This guide documents how to integrate with Jira and Confluence APIs for project documentation and tracking. The APIs use different authentication methods and data formats.

**Date Created**: September 27, 2025
**API Version**: Atlassian Cloud REST API v3 (Jira) / v1 (Confluence)

## Authentication

### API Token Setup
1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Create API token with full permissions
3. Store in `.env` file:
```env
ATLASSIAN_EMAIL="your-email@domain.com"
ATLASSIAN_API_TOKEN="ATATT3xFfGF..."
ATLASSIAN_DOMAIN="your-domain.atlassian.net"
```

### Authentication Header
```python
import base64
auth_string = f'{email}:{token}'
auth_header = base64.b64encode(auth_string.encode()).decode()
headers = {
    'Authorization': f'Basic {auth_header}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}
```

## Jira API Integration

### Base URLs
- **REST API**: `https://your-domain.atlassian.net/rest/api/3/`
- **Issue Creation**: `POST /rest/api/3/issue`
- **Issue Search**: `POST /rest/api/3/search/jql`

### Key Endpoints

#### 1. Get User Information
```python
GET /rest/api/3/myself
```

#### 2. List Projects
```python
GET /rest/api/3/project
```

#### 3. Search Issues
```python
POST /rest/api/3/search/jql
{
    "jql": "project = CCS ORDER BY updated DESC",
    "maxResults": 20,
    "fields": ["summary", "status", "issuetype", "assignee"]
}
```

#### 4. Create Issue (Story)
```python
POST /rest/api/3/issue
{
    "fields": {
        "project": {"key": "CCS"},
        "summary": "Issue title",
        "description": { ... },  # ADF format
        "issuetype": {"name": "Story"},
        "priority": {"name": "High"}
    }
}
```

### Atlassian Document Format (ADF)

**Important**: Jira API v3 requires Atlassian Document Format instead of plain text or Wiki markup.

#### Basic ADF Structure
```python
adf_description = {
    "version": 1,
    "type": "doc",
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [
                {
                    "type": "text",
                    "text": "Heading Text"
                }
            ]
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Regular paragraph text"
                }
            ]
        },
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Bullet point item"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}
```

#### ADF Elements Reference

**Panel (Success/Info/Warning/Error)**:
```python
{
    "type": "panel",
    "attrs": {
        "panelType": "success"  # or "info", "warning", "error"
    },
    "content": [
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Panel content",
                    "marks": [{"type": "strong"}]  # Bold text
                }
            ]
        }
    ]
}
```

**Links**:
```python
{
    "type": "text",
    "text": "Link text",
    "marks": [
        {
            "type": "link",
            "attrs": {
                "href": "https://example.com"
            }
        }
    ]
}
```

**Code Block**:
```python
{
    "type": "codeBlock",
    "attrs": {
        "language": "bash"
    },
    "content": [
        {
            "type": "text",
            "text": "git push origin main"
        }
    ]
}
```

### Issue Transitions
```python
# Get available transitions
GET /rest/api/3/issue/{issueKey}/transitions

# Execute transition
POST /rest/api/3/issue/{issueKey}/transitions
{
    "transition": {"id": "31"}  # Transition ID
}
```

## Confluence API Integration

### Base URLs
- **REST API**: `https://your-domain.atlassian.net/wiki/rest/api/`
- **Create Page**: `POST /wiki/rest/api/content`
- **List Spaces**: `GET /wiki/rest/api/space`

### Key Endpoints

#### 1. List Spaces
```python
GET /wiki/rest/api/space
```

#### 2. Create Page
```python
POST /wiki/rest/api/content
{
    "type": "page",
    "title": "Page Title",
    "space": {"key": "SPACE_KEY"},
    "body": {
        "storage": {
            "value": "<html content>",
            "representation": "storage"
        }
    }
}
```

### Confluence Storage Format

Confluence uses **Storage Format** (XHTML-based) for page content:

```html
<h1>Main Heading</h1>

<ac:structured-macro ac:name="panel" ac:schema-version="1">
<ac:parameter ac:name="panelType">success</ac:parameter>
<ac:rich-text-body>
<p><strong>Status:</strong> ✅ Completed</p>
</ac:rich-text-body>
</ac:structured-macro>

<h2>Section Heading</h2>
<ul>
<li>Bullet point 1</li>
<li>Bullet point 2</li>
</ul>

<ac:structured-macro ac:name="code" ac:schema-version="1">
<ac:parameter ac:name="language">bash</ac:parameter>
<ac:rich-text-body>
<p>git push origin main</p>
</ac:rich-text-body>
</ac:structured-macro>
```

#### Common Confluence Macros

**Info/Tip/Note Panel**:
```html
<ac:structured-macro ac:name="tip" ac:schema-version="1">
<ac:rich-text-body>
<p>Tip content here</p>
</ac:rich-text-body>
</ac:structured-macro>
```

**Code Block**:
```html
<ac:structured-macro ac:name="code" ac:schema-version="1">
<ac:parameter ac:name="language">python</ac:parameter>
<ac:rich-text-body>
<p>def hello_world():</p>
<p>    print("Hello, World!")</p>
</ac:rich-text-body>
</ac:structured-macro>
```

## Complete Example: Creating Jira Story

```python
import requests
import base64

# Authentication
email = 'your-email@domain.com'
token = 'your-api-token'
auth_string = f'{email}:{token}'
auth_header = base64.b64encode(auth_string.encode()).decode()

headers = {
    'Authorization': f'Basic {auth_header}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# ADF Description
adf_description = {
    "version": 1,
    "type": "doc",
    "content": [
        {
            "type": "panel",
            "attrs": {"panelType": "success"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Completed: Feature implementation",
                            "marks": [{"type": "strong"}]
                        }
                    ]
                }
            ]
        },
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "Overview"}]
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Description of the work completed."}
            ]
        }
    ]
}

# Create Story
story_data = {
    "fields": {
        "project": {"key": "PROJECT_KEY"},
        "summary": "Story Title",
        "description": adf_description,
        "issuetype": {"name": "Story"},
        "priority": {"name": "High"}
    }
}

response = requests.post(
    'https://your-domain.atlassian.net/rest/api/3/issue',
    headers=headers,
    json=story_data
)

if response.status_code == 201:
    result = response.json()
    print(f"Created issue: {result['key']}")
```

## Complete Example: Creating Confluence Page

```python
page_content = '''
<h1>Page Title</h1>

<ac:structured-macro ac:name="panel" ac:schema-version="1">
<ac:parameter ac:name="panelType">info</ac:parameter>
<ac:rich-text-body>
<p><strong>Status:</strong> Documentation</p>
</ac:rich-text-body>
</ac:structured-macro>

<h2>Section</h2>
<ul>
<li>Point 1</li>
<li>Point 2</li>
</ul>
'''

page_data = {
    "type": "page",
    "title": "My Documentation Page",
    "space": {"key": "SPACE_KEY"},
    "body": {
        "storage": {
            "value": page_content,
            "representation": "storage"
        }
    }
}

response = requests.post(
    'https://your-domain.atlassian.net/wiki/rest/api/content',
    headers=headers,
    json=page_data
)

if response.status_code == 200:
    result = response.json()
    page_url = f"https://your-domain.atlassian.net/wiki/spaces/{space_key}/pages/{result['id']}"
    print(f"Created page: {page_url}")
```

## Error Handling

### Common Errors

**401 Unauthorized**:
- Check API token validity
- Verify email address is correct
- Ensure token has necessary permissions

**400 Bad Request (Jira)**:
- Usually ADF format issues
- Check required fields are present
- Validate project key and issue type

**403 Forbidden**:
- User lacks permissions for the operation
- Check project/space permissions in Atlassian

### Debug Tips

1. **Test Authentication First**:
```python
response = requests.get(
    'https://your-domain.atlassian.net/rest/api/3/myself',
    headers=headers
)
```

2. **Validate ADF Format**:
   - Use simple text first, then add formatting
   - Check for missing required fields
   - Ensure proper nesting of content elements

3. **Check Available Projects/Spaces**:
```python
# Jira projects
projects = requests.get(
    'https://your-domain.atlassian.net/rest/api/3/project',
    headers=headers
).json()

# Confluence spaces
spaces = requests.get(
    'https://your-domain.atlassian.net/wiki/rest/api/space',
    headers=headers
).json()
```

## Best Practices

1. **Environment Variables**: Store credentials securely in `.env`
2. **Error Handling**: Always check response status codes
3. **Rate Limiting**: Implement delays for bulk operations
4. **Testing**: Test with simple content before complex formatting
5. **Documentation**: Include links between Jira issues and Confluence pages

## Integration Patterns

### Project Workflow
1. Create Jira Epic for major features
2. Break down into Stories and Tasks
3. Create Confluence page for technical documentation
4. Link Jira issues to Confluence pages
5. Update status as work progresses

### Automation
- Trigger documentation updates on code deployments
- Create Jira issues from CI/CD pipeline failures
- Update Confluence pages with deployment status

## Useful Resources

- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [Confluence REST API Documentation](https://developer.atlassian.com/cloud/confluence/rest/v1/)
- [Atlassian Document Format](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
- [Confluence Storage Format](https://confluence.atlassian.com/conf59/confluence-storage-format-792499894.html)