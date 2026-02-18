# Repository Patterns Guide

FastStack provides a sophisticated multi-layer repository architecture that supports raw SQL, ORM operations, external databases, and centralized repository management. This guide covers all repository patterns and best practices.

## Repository Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layers                       │
├─────────────────────────────────────────────────────────────┤
│  AbstractRepository (Raw SQL + Security)                   │
│  ├── BaseRepository (ORM + Soft Delete)                    │
│  └── ExternalBaseRepository (External DBs)                 │
├─────────────────────────────────────────────────────────────┤
│  RepositoryManager (Centralized Access)                    │
└─────────────────────────────────────────────────────────────┘
```

## AbstractRepository - Raw SQL Foundation

The `AbstractRepository` provides secure raw SQL execution with built-in security validation and flexible output formats.

### Basic Usage

```python
from faststack.repositories.abstract_repository import AbstractRepository
from faststack.schemas.pagination_model import PaginationParams

class AnalyticsRepository(AbstractRepository):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    def get_user_analytics(self, user_id: int) -> dict:
        query = """
            SELECT
                COUNT(*) as total_posts,
                AVG(views) as avg_views,
                MAX(created_at) as last_post_date
            FROM posts
            WHERE author_id = :user_id
        """

        result = self.fetchone(
            query,
            params={"user_id": user_id},
            dataframe=False
        )
        return dict(result) if result else {}
```

### Security Features

FastStack automatically validates SQL queries to prevent dangerous operations:

```python
# ✅ Allowed queries
"SELECT * FROM users WHERE id = :id"
"WITH recent_posts AS (...) SELECT * FROM recent_posts"
"SELECT * FROM table1 UNION SELECT * FROM table2"

# ❌ Blocked queries
"DROP TABLE users"           # DDL operations blocked
"UPDATE users SET ..."       # DML operations blocked
"INSERT INTO users ..."      # Insert operations blocked
"DELETE FROM users ..."      # Delete operations blocked
```

### Flexible Output Formats

```python
class ReportRepository(AbstractRepository):
    def get_monthly_report(self, month: int, year: int) -> pd.DataFrame:
        query = """
            SELECT
                DATE_TRUNC('day', created_at) as date,
                COUNT(*) as daily_count,
                SUM(amount) as daily_revenue
            FROM orders
            WHERE EXTRACT(month FROM created_at) = :month
              AND EXTRACT(year FROM created_at) = :year
            GROUP BY DATE_TRUNC('day', created_at)
            ORDER BY date
        """

        # Return as pandas DataFrame
        return self.execute_df_query(
            query,
            params={"month": month, "year": year},
            return_type=pd.DataFrame  # or pl.DataFrame for Polars
        )

    def get_paginated_orders(self, pagination: PaginationParams) -> PaginatedList:
        query = "SELECT * FROM orders ORDER BY created_at DESC"

        # Automatic pagination with count
        return self.fetch_paginated(
            query=query,
            pagination=pagination
        )

    def get_order_summary(self, order_id: int) -> OrderSummaryModel:
        query = """
            SELECT
                o.id,
                o.total_amount,
                u.email as customer_email,
                COUNT(oi.id) as item_count
            FROM orders o
            JOIN users u ON o.user_id = u.id
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.id = :order_id
            GROUP BY o.id, o.total_amount, u.email
        """

        # Return as Pydantic model
        return self.fetchone(
            query,
            params={"order_id": order_id},
            model=OrderSummaryModel
        )
```

### Dynamic Query Building

```python
class SearchRepository(AbstractRepository):
    def search_products(
        self,
        category_filters: list[str] = None,
        price_min: float = None,
        price_max: float = None,
        pagination: PaginationParams = None
    ) -> PaginatedList:

        # Base query
        base_query = """
            SELECT p.*, c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
        """

        # Build dynamic filters
        filters = []
        params = {}

        if category_filters:
            placeholders, params = self._placeholders_and_params(
                category_filters,
                "category",
                params
            )
            filters.append(f"c.name IN ({','.join(placeholders)})")

        if price_min is not None:
            filters.append("p.price >= :price_min")
            params["price_min"] = price_min

        if price_max is not None:
            filters.append("p.price <= :price_max")
            params["price_max"] = price_max

        # Build WHERE clause
        where_clause = self._create_filter_condition(filters, [])
        final_query = base_query + where_clause + " ORDER BY p.created_at DESC"

        return self.fetch_paginated(
            query=final_query,
            pagination=pagination or PaginationParams(limit=20, offset=0),
            params=params
        )
```

## BaseRepository - ORM with Business Logic

The `BaseRepository` provides full CRUD operations with automatic soft delete support and type safety.

### Basic CRUD Operations

```python
from faststack.repositories.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    def find_by_email(self, email: str) -> User | None:
        """Find user by email with soft delete awareness."""
        return self.filter_one(email=email)
        # Automatically adds: WHERE deleted_at IS NULL

    def get_active_users_count(self) -> int:
        """Count active users."""
        return self.count_by()  # Soft delete filtering automatic

    def search_users(self, search_term: str) -> list[User]:
        """Search users by name or email."""
        filters = [
            User.email.ilike(f"%{search_term}%"),
            User.full_name.ilike(f"%{search_term}%")
        ]
        # OR condition: email LIKE '%term%' OR full_name LIKE '%term%'
        return self.filter_by(*filters)

    def get_users_by_role(self, role: UserRole) -> list[User]:
        """Get users with specific role."""
        return self.filter_by(User.role == role)
```

### Soft Delete Operations

```python
class PostRepository(BaseRepository[Post]):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    def soft_delete_post(self, post_id: int) -> bool:
        """Soft delete a post."""
        post = self.get_by_id(post_id)
        if not post:
            return False

        self.soft_delete(post, commit=True)
        return True

    def bulk_soft_delete_old_posts(self, cutoff_date: datetime) -> int:
        """Soft delete posts older than cutoff date."""
        old_posts = self.filter_by(Post.created_at < cutoff_date)
        post_ids = [post.id for post in old_posts]

        if post_ids:
            self.bulk_soft_delete(post_ids, commit=True)

        return len(post_ids)

    def restore_post(self, post_id: int) -> bool:
        """Restore a soft-deleted post."""
        # Note: You'll need to implement restore functionality
        # or query including soft-deleted records
        post = self.db.query(Post).filter(
            Post.id == post_id,
            Post.deleted_at.is_not(None)
        ).first()

        if post:
            post.deleted_at = None
            self.db.add(post)
            self.commit()
            return True
        return False
```

### Advanced Query Patterns

```python
class OrderRepository(BaseRepository[Order]):
    def get_user_orders_with_totals(self, user_id: int) -> list[dict]:
        """Get user orders with calculated totals."""
        from sqlalchemy import func

        result = (
            self.db.query(
                Order.id,
                Order.status,
                Order.created_at,
                func.sum(OrderItem.quantity * OrderItem.price).label('total_amount'),
                func.count(OrderItem.id).label('item_count')
            )
            .join(OrderItem, Order.id == OrderItem.order_id)
            .filter(Order.user_id == user_id)
            .group_by(Order.id, Order.status, Order.created_at)
            .all()
        )

        return [
            {
                "id": row.id,
                "status": row.status.value,
                "created_at": row.created_at,
                "total_amount": float(row.total_amount or 0),
                "item_count": row.item_count
            }
            for row in result
        ]

    def get_orders_by_date_range(
        self,
        start_date: date,
        end_date: date,
        status_filter: OrderStatus = None
    ) -> list[Order]:
        """Get orders within date range with optional status filter."""
        filters = [
            Order.created_at >= start_date,
            Order.created_at <= end_date
        ]

        if status_filter:
            filters.append(Order.status == status_filter)

        return self.filter_by(filters)
```

### Generic Model Extraction

FastStack automatically extracts the model type from your repository:

```python
class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)
        # self.model is automatically set to User

    def create_user_with_validation(self, user_data: dict) -> User:
        """Create user with model-specific validation."""
        # self.model is available and typed as Type[User]
        if self.find_by_email(user_data["email"]):
            raise ValueError("Email already exists")

        user = self.model(**user_data)  # self.model = User
        return self.create(user, commit=True)
```

## ExternalBaseRepository - External Database Access

For connecting to external systems like data warehouses, analytics databases, or third-party systems:

```python
from faststack.repositories.external_base_repository import ExternalBaseRepository

class DataWarehouseRepository(ExternalBaseRepository):
    def __init__(self, db: DataWarehouseSession, profiler: Profiler):
        super().__init__(db, profiler)

    def get_monthly_analytics(self, month: int, year: int) -> pd.DataFrame:
        """Get analytics data from data warehouse."""
        query = """
            SELECT
                metric_name,
                metric_value,
                dimension1,
                dimension2,
                recorded_date
            FROM analytics.monthly_metrics
            WHERE month_num = :month AND year_num = :year
            ORDER BY recorded_date DESC
        """

        return self.execute_df_query(
            query,
            params={"month": month, "year": year}
        )

class LegacySystemRepository(ExternalBaseRepository):
    def __init__(self, db: LegacySession, profiler: Profiler):
        super().__init__(db, profiler)

    def sync_customer_data(self, customer_ids: list[int]) -> list[dict]:
        """Sync customer data from legacy system."""
        placeholders, params = self._placeholders_and_params(
            customer_ids,
            "customer_id",
            {}
        )

        query = f"""
            SELECT
                customer_id,
                customer_name,
                last_updated,
                status
            FROM legacy.customers
            WHERE customer_id IN ({','.join(placeholders)})
        """

        return self.fetch_list(query, params)
```

## RepositoryManager - Centralized Access

The `RepositoryManager` provides centralized access to multiple repositories with shared session management:

### Basic Repository Manager

```python
from faststack.repositories.repository_manager import RepositoryManager

class UserDomainManager(RepositoryManager[Session]):
    """Manages all user-related repositories."""

    def get_user_repo(self) -> UserRepository:
        return self.get(UserRepository)

    def get_profile_repo(self) -> ProfileRepository:
        return self.get(ProfileRepository)

    def get_notification_repo(self) -> NotificationRepository:
        return self.get(NotificationRepository)

# Usage in service
class UserService(BaseService):
    def __init__(self, user_domain: UserDomainManager):
        self.user_domain = user_domain

    def create_user_with_profile(self, user_data: dict, profile_data: dict) -> User:
        """Create user and profile in single transaction."""
        user_repo = self.user_domain.get_user_repo()
        profile_repo = self.user_domain.get_profile_repo()

        # Both repositories share the same database session
        user = user_repo.create(User(**user_data), flush=True, commit=False)

        profile_data["user_id"] = user.id
        profile = profile_repo.create(Profile(**profile_data), flush=True, commit=False)

        # Commit both operations together
        self.user_domain.commit()

        return user
```

### Multi-Database Repository Manager

```python
# Different managers for different databases
class PrimaryDomainManager(RepositoryManager[PrimarySession]):
    """Main application database repositories."""

    def get_user_repo(self) -> UserRepository:
        return self.get(UserRepository)

    def get_order_repo(self) -> OrderRepository:
        return self.get(OrderRepository)

class AnalyticsDomainManager(RepositoryManager[AnalyticsSession]):
    """Analytics database repositories."""

    def get_event_repo(self) -> EventRepository:
        return self.get(EventRepository)

    def get_metrics_repo(self) -> MetricsRepository:
        return self.get(MetricsRepository)

# Service using multiple managers
class ReportService(BaseService):
    def __init__(
        self,
        primary_domain: PrimaryDomainManager,
        analytics_domain: AnalyticsDomainManager
    ):
        self.primary_domain = primary_domain
        self.analytics_domain = analytics_domain

    def generate_user_report(self, user_id: int) -> dict:
        """Generate report using data from multiple databases."""
        user_repo = self.primary_domain.get_user_repo()
        order_repo = self.primary_domain.get_order_repo()
        event_repo = self.analytics_domain.get_event_repo()

        user = user_repo.get_by_id(user_id)
        orders = order_repo.get_orders_by_user(user_id)
        events = event_repo.get_user_events(user_id)

        return {
            "user": user,
            "order_summary": self._summarize_orders(orders),
            "activity_summary": self._summarize_events(events)
        }
```

## Async Repository Patterns

FastStack supports full async operations for high-performance applications:

```python
class AsyncUserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession, profiler: Profiler):
        super().__init__(db, profiler)

    async def find_user_by_email(self, email: str) -> User | None:
        """Async user lookup."""
        return await self.afilter_one(email=email)

    async def create_user_async(self, user_data: dict) -> User:
        """Create user asynchronously."""
        user = User(**user_data)
        return await self.acreate(user, commit=True)

    async def bulk_update_last_login(self, user_ids: list[int]) -> None:
        """Bulk update last login timestamps."""
        from sqlalchemy import update

        stmt = (
            update(User)
            .where(User.id.in_(user_ids))
            .values(last_login_at=datetime.utcnow())
        )

        await self.db.execute(stmt)
        await self.acommit()

# Async service usage
class AsyncUserService(BaseService):
    def __init__(self, user_repo: AsyncUserRepository):
        self.user_repo = user_repo

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """Authenticate user asynchronously."""
        user = await self.user_repo.find_user_by_email(email)

        if user and verify_password(password, user.password_hash):
            # Update last login in background
            await self.user_repo.bulk_update_last_login([user.id])
            return user

        return None
```

## Advanced Patterns

### Repository with Caching

Combine repositories with caching for better performance:

```python
from faststack.cache.cache_decorater import cache_method_async

class CachedUserRepository(BaseRepository[User]):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    @cache_method_async(expire=300, key_prefix="user_repo", version="v1")
    async def get_user_by_id_cached(self, user_id: int) -> User | None:
        """Get user with caching."""
        return self.get_by_id(user_id)

    @cache_method_async(expire=600, key_prefix="user_repo", version="v1")
    async def get_active_users_cached(self) -> list[User]:
        """Get active users with caching."""
        return self.filter_by()

    def invalidate_user_cache(self, user_id: int):
        """Invalidate cache when user is updated."""
        # Implementation depends on your cache strategy
        pass
```

### Repository with Event Publishing

Integrate repositories with event systems:

```python
class EventPublishingUserRepository(BaseRepository[User]):
    def __init__(self, db: Session, profiler: Profiler, event_publisher: EventPublisher):
        super().__init__(db, profiler)
        self.event_publisher = event_publisher

    def create_user_with_events(self, user_data: dict) -> User:
        """Create user and publish events."""
        user = self.create(User(**user_data), commit=True)

        # Publish user created event
        self.event_publisher.publish(
            "user.created",
            {"user_id": user.id, "email": user.email}
        )

        return user

    def soft_delete_user_with_events(self, user_id: int) -> bool:
        """Soft delete user and publish events."""
        user = self.get_by_id(user_id)
        if not user:
            return False

        self.soft_delete(user, commit=True)

        # Publish user deleted event
        self.event_publisher.publish(
            "user.deleted",
            {"user_id": user.id, "email": user.email}
        )

        return True
```

## Best Practices

### 1. Choose the Right Repository Level

```python
# ✅ Use AbstractRepository for complex analytical queries
class AnalyticsRepository(AbstractRepository):
    def get_complex_metrics(self) -> pd.DataFrame:
        # Complex SQL with joins, CTEs, window functions
        pass

# ✅ Use BaseRepository for standard CRUD operations
class UserRepository(BaseRepository[User]):
    def find_by_email(self, email: str) -> User | None:
        return self.filter_one(email=email)

# ✅ Use ExternalBaseRepository for external systems
class DataWarehouseRepository(ExternalBaseRepository):
    def sync_external_data(self) -> list[dict]:
        pass
```

### 2. Leverage Repository Managers

```python
# ✅ Group related repositories
class OrderDomainManager(RepositoryManager[Session]):
    def get_order_repo(self) -> OrderRepository:
        return self.get(OrderRepository)

    def get_order_item_repo(self) -> OrderItemRepository:
        return self.get(OrderItemRepository)

    def get_payment_repo(self) -> PaymentRepository:
        return self.get(PaymentRepository)

# ❌ Don't inject too many individual repositories
class OrderService(BaseService):
    def __init__(self, order_repo, item_repo, payment_repo, user_repo, product_repo):
        pass  # Too many dependencies
```

### 3. Use Appropriate Session Types

```python
# ✅ Use specific session types for different purposes
class UserRepository(BaseRepository[User]):
    def __init__(self, db: PrimarySession, profiler: Profiler):  # Main DB
        super().__init__(db, profiler)

class AnalyticsRepository(AbstractRepository):
    def __init__(self, db: AnalyticsSession, profiler: Profiler):  # Analytics DB
        super().__init__(db, profiler)
```

### 4. Handle Transactions Properly

```python
# ✅ Use repository manager for multi-repository transactions
def create_order_with_items(self, order_data: dict, items: list[dict]) -> Order:
    order_repo = self.order_domain.get_order_repo()
    item_repo = self.order_domain.get_order_item_repo()

    order = order_repo.create(Order(**order_data), commit=False)

    for item_data in items:
        item_data["order_id"] = order.id
        item_repo.create(OrderItem(**item_data), commit=False)

    self.order_domain.commit()  # Commit all changes together
    return order

# ❌ Don't mix commits across repositories
def bad_create_order(self, order_data: dict, items: list[dict]):
    order = order_repo.create(Order(**order_data), commit=True)  # Committed

    for item_data in items:
        item_repo.create(OrderItem(**item_data), commit=True)  # Separate commits
    # If later items fail, order is already committed!
```

## Next Steps

- **[Service Architecture](services.md)** - Build services on top of repositories
- **[Caching Strategies](caching.md)** - Add caching to repositories
- **[Testing Repositories](testing.md)** - Test repository implementations
- **[Performance Optimization](performance.md)** - Optimize repository performance