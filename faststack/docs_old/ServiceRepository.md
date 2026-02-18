# Service-Repository Pattern in FastStack

The Service-Repository pattern is a design pattern that separates business logic (services) from data access logic (repositories). This pattern promotes clean architecture, maintainability, and testability by creating clear boundaries between different layers of the application.

## Pattern Overview

### Repository Layer
- **Responsibility**: Data access and persistence operations
- **Contains**: CRUD operations, database queries, data mapping
- **Abstracts**: Database-specific implementation details

### Service Layer
- **Responsibility**: Business logic and orchestration
- **Contains**: Business rules, validation, workflow coordination
- **Orchestrates**: Multiple repositories and external services

## Architecture in FastStack

```
┌─────────────────┐    ┌─────────────────┐
│   Controller    │───▶│    Service      │
│   (FastAPI)     │    │   (Business)    │
└─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Repository    │
                       │  (Data Access)  │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │    Database     │
                       └─────────────────┘
```

## Repository Implementation

### Base Repository

Every repository in FastStack extends `AbstractRepository`:

```python
from faststack.repositories.abstract_repository import AbstractRepository
from sqlalchemy.orm import Session

class UserRepository(AbstractRepository[User]):
    """Repository for User entity operations."""
    def find_by_email(self, email: str) -> User | None:
        """Find user by email address."""
        return self.db.query(User).filter(User.email == email).first()

    def find_active_users(self) -> list[User]:
        """Find all active users."""
        return self.db.query(User).filter(User.is_active == True).all()

    def create_user(self, user_data: dict) -> User:
        """Create a new user."""
        user = User(**user_data)
        self.db.add(user)
        self.db.flush()
        return user
```

### Repository Features

- **Generic Type Safety**: `AbstractRepository[T]` provides type hints for the entity
- **Built-in CRUD**: Inherits common operations like `create()`, `update()`, `delete()`, `get()`
- **Session Management**: Handles database session lifecycle
- **Profiling Support**: Integrated performance monitoring

## Service Implementation

Services in FastStack can be implemented in two ways: using individual repositories or using a Repository Manager for coordinated operations.

### Option 1: Service with Individual Repositories

Every service extends `BaseService`:

```python
from faststack.services.base_service import BaseService
from faststack.dependencies.repositories import load_repository_dep

class UserService(BaseService):
    """Service for user business logic using individual repositories."""

    def __init__(self, user_repo: UserRepository = load_repository_dep(UserRepository)):
        self.user_repo = user_repo

    async def register_user(self, email: str, name: str) -> User:
        """Register a new user with business validation."""
        # Business rule: Check if user already exists
        existing_user = self.user_repo.find_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")

        # Business rule: Validate email format
        if not self._is_valid_email(email):
            raise ValueError("Invalid email format")

        # Create user through repository
        user_data = {
            "email": email,
            "name": name,
            "is_active": True,
            "created_at": datetime.utcnow()
        }

        user = self.user_repo.create_user(user_data)

        # Business logic: Send welcome email
        await self._send_welcome_email(user)

        return user

    def get_user_summary(self, user_id: int) -> dict:
        """Get user summary with business calculations."""
        user = self.user_repo.get(user_id)
        if not user:
            raise ValueError("User not found")

        # Business logic: Calculate user metrics
        return {
            "user": user,
            "account_age_days": (datetime.utcnow() - user.created_at).days,
            "is_premium": self._check_premium_status(user),
            "activity_score": self._calculate_activity_score(user)
        }

    def _is_valid_email(self, email: str) -> bool:
        """Business validation for email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    async def _send_welcome_email(self, user: User):
        """Send welcome email (business process)."""
        # Implementation for sending email
        pass

    def _check_premium_status(self, user: User) -> bool:
        """Check if user has premium status."""
        # Business logic implementation
        return False

    def _calculate_activity_score(self, user: User) -> float:
        """Calculate user activity score."""
        # Business logic implementation
        return 0.0
```

## Multi-Repository Services

Services often need to coordinate multiple repositories:

```python
class OrderService(BaseService):
    """Service for order business logic."""

    def __init__(
        self,
        order_repo: OrderRepository = load_repository_dep(OrderRepository),
        user_repo: UserRepository = load_repository_dep(UserRepository),
        inventory_repo: InventoryRepository = load_repository_dep(InventoryRepository),
        payment_repo: PaymentRepository = load_repository_dep(PaymentRepository)
    ):
        self.order_repo = order_repo
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.payment_repo = payment_repo

    async def create_order(self, user_id: int, items: list[dict]) -> Order:
        """Create order with complex business logic."""
        try:
            # Validate user exists and is active
            user = self.user_repo.get(user_id)
            if not user or not user.is_active:
                raise ValueError("Invalid or inactive user")

            # Check inventory availability
            for item in items:
                if not self.inventory_repo.is_available(item['product_id'], item['quantity']):
                    raise ValueError(f"Product {item['product_id']} not available")

            # Calculate total amount
            total_amount = self._calculate_total(items)

            # Create order
            order_data = {
                "user_id": user_id,
                "status": "pending",
                "total_amount": total_amount,
                "created_at": datetime.utcnow()
            }

            order = self.order_repo.create(order_data)

            # Reserve inventory
            for item in items:
                self.inventory_repo.reserve(item['product_id'], item['quantity'])

            # Process payment
            payment = await self._process_payment(order, total_amount)
            self.payment_repo.create(payment)

            # Update order status
            self.order_repo.update(order.id, {"status": "confirmed"})

            return order

        except Exception:
            # Rollback logic would be handled at the transaction level
            raise

    def _calculate_total(self, items: list[dict]) -> decimal.Decimal:
        """Calculate order total with business rules."""
        # Implementation with discounts, taxes, etc.
        pass

    async def _process_payment(self, order: Order, amount: decimal.Decimal) -> dict:
        """Process payment through external service."""
        # Implementation
        pass
```

## Repository Manager Integration

For complex operations involving multiple repositories, use `RepositoryManager`:

```python
class OrderService(BaseService):
    def __init__(self, repo_manager: OrderRepositoryManager):
        self.repo_manager = repo_manager

    async def create_order(self, user_id: int, items: list[dict]) -> Order:
        """Create order using repository manager for transaction management."""
        try:
            # Get all repositories from manager
            order_repo = self.repo_manager.get(OrderRepository)
            user_repo = self.repo_manager.get(UserRepository)
            inventory_repo = self.repo_manager.get(InventoryRepository)

            # Perform business operations
            user = user_repo.get(user_id)
            # ... business logic ...

            order = order_repo.create(order_data)

            for item in items:
                inventory_repo.reserve(item['product_id'], item['quantity'])

            # Commit all changes in single transaction
            self.repo_manager.commit()

            return order

        except Exception:
            self.repo_manager.rollback()
            raise
```

## Dependency Injection

### In FastAPI Controllers

```python
from fastapi import FastAPI, Depends
from faststack.dependencies.services import load_service_dep

app = FastAPI()

@app.post("/users")
async def create_user(
    user_data: UserCreateModel,
    user_service: UserService = load_service_dep(UserService)
):
    """Create user endpoint."""
    try:
        user = await user_service.register_user(user_data.email, user_data.name)
        return {"user": user, "message": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    user_service: UserService = load_service_dep(UserService)
):
    """Get user endpoint."""
    try:
        user_summary = user_service.get_user_summary(user_id)
        return user_summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

### In Celery Tasks

```python
from faststack.dependencies.services import load_service

@celery_app.task
def process_daily_reports():
    """Celery task using service layer."""
    # Load service outside FastAPI context
    user_service = load_service(UserService)
    report_service = load_service(ReportService)

    # Use business logic through services
    active_users = user_service.get_active_users()
    report_service.generate_daily_report(active_users)
```

## Testing the Pattern

### Repository Testing

```python
import pytest
from unittest.mock import MagicMock

def test_user_repository_find_by_email():
    # Mock database session
    mock_db = MagicMock()
    mock_profiler = MagicMock()

    # Create repository with mocked dependencies
    repo = UserRepository(mock_db, mock_profiler)

    # Test repository method
    result = repo.find_by_email("test@example.com")

    # Assert database query was called correctly
    mock_db.query.assert_called_once_with(User)
```

### Service Testing

```python
import pytest
from unittest.mock import MagicMock

def test_user_service_register_user():
    # Mock repository
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_email.return_value = None  # No existing user

    # Create service with mocked repository
    service = UserService(mock_user_repo)

    # Test service method
    result = await service.register_user("test@example.com", "Test User")

    # Assert repository was called correctly
    mock_user_repo.find_by_email.assert_called_once_with("test@example.com")
    mock_user_repo.create_user.assert_called_once()
```

## Benefits of the Pattern

### 1. Separation of Concerns
- **Repositories**: Focus only on data access
- **Services**: Focus only on business logic
- **Controllers**: Focus only on HTTP handling

### 2. Testability
- Easy to mock repositories in service tests
- Easy to test business logic in isolation
- Clear test boundaries

### 3. Maintainability
- Changes to business logic don't affect data access
- Changes to data access don't affect business logic
- Clear code organization

### 4. Reusability
- Services can be used in different contexts (API, background tasks, etc.)
- Repositories can be shared across multiple services
- Business logic is centralized

### 5. Dependency Injection
- Flexible dependency management
- Easy to swap implementations
- Supports both FastAPI and non-FastAPI contexts

## Best Practices

### 1. Keep Repositories Thin
```python
# Good: Simple data access
class UserRepository(AbstractRepository[User]):
    def find_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

# Bad: Business logic in repository
class UserRepository(AbstractRepository[User]):
    def register_user(self, email: str, name: str) -> User:
        # Validation logic belongs in service layer
        if not self._is_valid_email(email):
            raise ValueError("Invalid email")
        # ...
```

### 2. Keep Services Rich
```python
# Good: Rich business logic
class UserService(BaseService):
    async def register_user(self, email: str, name: str) -> User:
        # Complex business validation and orchestration
        existing_user = self.user_repo.find_by_email(email)
        if existing_user:
            raise ValueError("User already exists")

        # Multiple steps of business logic
        user = self.user_repo.create_user({"email": email, "name": name})
        await self._send_welcome_email(user)
        await self._create_user_profile(user)

        return user
```

### 3. Use Repository Manager for Transactions
```python
# Good: Single transaction for multiple repositories
class OrderService(BaseService):
    def __init__(self, repo_manager: OrderRepositoryManager):
        self.repo_manager = repo_manager

    async def create_order(self, data: dict):
        try:
            # All operations in single transaction
            order_repo = self.repo_manager.get(OrderRepository)
            inventory_repo = self.repo_manager.get(InventoryRepository)

            order = order_repo.create(data)
            inventory_repo.reserve_items(data['items'])

            self.repo_manager.commit()
        except Exception:
            self.repo_manager.rollback()
            raise
```

### 4. Handle Errors Appropriately
```python
class UserService(BaseService):
    async def register_user(self, email: str, name: str) -> User:
        try:
            # Business validation
            if not self._is_valid_email(email):
                raise ValueError("Invalid email format")  # Business error

            # Repository operation
            user = self.user_repo.create_user({"email": email, "name": name})

            return user
        except IntegrityError:
            # Convert database error to business error
            raise ValueError("User with this email already exists")
```

## Real-World Example: Service with Repository Manager

Here's a practical example of how services use Repository Manager in FastStack:

```python
from faststack.services.base_service import BaseService
from faststack.dependencies.repository_manager import repository_manager_dep

class RepositoryManagerLocal(RepositoryManager[Session]):
    """Local repository manager for coordinated operations."""
    pass

class TestRepositoryManagerService(BaseService):
    """Service using Repository Manager for coordinated operations."""

    def __init__(self, rm: RepositoryManagerLocal = repository_manager_dep(RepositoryManagerLocal)):
        self.rm = rm

    def process_business_operation(self, data: dict):
        """Example business operation using multiple repositories."""
        try:
            # Get repositories through manager
            user_repo = self.rm.get(UserRepository)
            order_repo = self.rm.get(OrderRepository)
            audit_repo = self.rm.get(AuditRepository)

            # Perform coordinated operations
            user = user_repo.create(data['user_data'])
            self.rm.flush()  # Get user.id

            order = order_repo.create({
                'user_id': user.id,
                'items': data['order_items']
            })

            audit_repo.log_action('business_operation', {
                'user_id': user.id,
                'order_id': order.id
            })

            # Commit all changes together
            self.rm.commit()

            return {'user': user, 'order': order}

        except Exception:
            # Rollback all changes on error
            self.rm.rollback()
            raise
```

**Key Benefits of This Approach:**
- **Single Transaction**: All repository operations share the same database session
- **Easy Rollback**: One command rolls back all changes if anything fails
- **Repository Access**: Clean access to any repository through `self.rm.get()`
- **Dependency Injection**: Automatic injection using `repository_manager_dep()`

The Service-Repository pattern in FastStack provides a clean, maintainable, and testable architecture for building robust applications with clear separation between business logic and data access.


