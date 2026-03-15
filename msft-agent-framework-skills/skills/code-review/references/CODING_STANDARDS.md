# Coding Standards Reference

## C# / .NET Standards

### Naming Conventions
- **PascalCase** for public members, types, namespaces
- **camelCase** for local variables, parameters
- **_camelCase** with underscore prefix for private fields
- **I** prefix for interfaces (e.g., `IRepository`)
- **Async** suffix for async methods (e.g., `GetUserAsync`)

### Patterns
- Use `async/await` consistently — never `.Result` or `.Wait()` in async code
- Prefer `IReadOnlyList<T>` over `List<T>` for return types
- Use `record` types for DTOs and value objects
- Implement `IDisposable` or use `using` statements for unmanaged resources
- Prefer pattern matching over type checking with `is` and `as`

### Error Handling
- Never swallow exceptions silently
- Use specific exception types, not bare `catch (Exception)`
- Validate public API parameters with `ArgumentNullException.ThrowIfNull()`

## Python Standards

### Naming Conventions
- **snake_case** for functions, variables, modules
- **PascalCase** for classes
- **UPPER_SNAKE_CASE** for constants
- Leading underscore `_` for private members

### Patterns
- Use type hints for function signatures
- Use context managers (`with`) for resource management
- Prefer f-strings for string formatting
- Use `pathlib.Path` instead of `os.path`
- Use dataclasses or Pydantic models for structured data

## JavaScript/TypeScript Standards

### Naming Conventions
- **camelCase** for variables, functions
- **PascalCase** for classes, interfaces, type aliases
- **UPPER_SNAKE_CASE** for constants

### Patterns
- Use `const` by default, `let` when reassignment is needed, never `var`
- Prefer `async/await` over `.then()` chains
- Use strict equality (`===`) always
- Destructure objects and arrays when extracting multiple values
- Use optional chaining (`?.`) and nullish coalescing (`??`)
