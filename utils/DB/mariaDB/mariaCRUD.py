
from utils import dict_to_object, setup_logger
from utils.config import settings
# bat 로거 초기화
sql_logger = setup_logger(name="sql_logger", log_file=f"{settings.LOG_DIR}/sql_queries.log")

class SQLBuilder:
    def __init__(self, table_name, instance):
        """
        SQLBuilder 클래스 초기화

        :param table_name: 사용할 테이블 이름
        :param instance: 데이터베이스 연결 객체
        """
        self.table_name = table_name
        self.query = ""
        self.params = []
        self.columns = "*"  # 기본적으로 모든 열 선택
        self.db_instance = instance

    def log_query(self):
        """현재 쿼리와 매개변수를 로그에 기록합니다."""
        sql_logger.debug("Generated SQL Query: %s", self.query)
        sql_logger.debug("With Parameters: %s", self.params)

    def _process_conditions(self, conditions):
        condition_clauses = []
        for key, value in conditions.items():
            if "__" in key:
                field, operator = key.split("__")
                sql_operator = {
                    "gte": ">=", "lte": "<=", "gt": ">", "lt": "<", 
                    "neq": "!=", "like": "LIKE", "in": "IN", "range": "BETWEEN"
                }.get(operator, "=")

                # `IN` 연산자 최적화
                if operator == "in":
                    if not value:  # 빈 리스트 방지
                        condition_clauses.append("FALSE")  # 항상 False가 되도록 처리
                    elif isinstance(value, list) and len(value) == 1:
                        # 단일 값이면 `IN` 대신 `=` 사용
                        condition_clauses.append(f"{field} = %s")
                        self.params.append(value[0])
                    else:
                        # 여러 개 값이면 `IN` 사용
                        placeholders = ", ".join(["%s"] * len(value))
                        condition_clauses.append(f"{field} IN ({placeholders})")
                        self.params.extend(value)

                # RANGE 연산자 (BETWEEN)
                elif operator == "range" and isinstance(value, list) and len(value) == 2:
                    condition_clauses.append(f"{field} BETWEEN %s AND %s")
                    self.params.extend(value)

                else:
                    condition_clauses.append(f"{field} {sql_operator} %s")
                    self.params.append(value)
            else:
                condition_clauses.append(f"{key}=%s")
                self.params.append(value)

        return " AND ".join(condition_clauses)

    def UPDATE(self, data=None, where=None):
        """
        UPDATE 쿼리를 생성합니다.

        :param data: 업데이트할 데이터 딕셔너리 (예: {"column1": "value1", "column2": "value2"})
        :param replace: REPLACE 기능을 위한 딕셔너리 (예: {"column": ("search_string", "replace_string")})
        :param where: 필터링 조건 딕셔너리 (예: {"column__like": "pattern"})
        :return: self

        query = SQLBuilder("t_table", db_instance).UPDATE(
            data={"name": "Jane Doe"},
            replace=("description", ("old_text", "new_text")),
            where={"id__eq": 1}
        )
        """

        set_clauses = [f"{key}=%s" for key in data.keys()]
        self.params.extend(data.values())

        self.query = f"UPDATE {self.table_name} SET {', '.join(set_clauses)}"

        if where:
            where_clause = self._process_conditions(where)
            self.query += f" WHERE {where_clause}"

        return self

    def EXISTS(self, conditions):
        """
        EXISTS 조건을 추가합니다.
        
        :param conditions: 조건 딕셔너리 (예: {"user_id": 1, "status": "active"})
        :return: self
        
        사용 예시:
        query = SQLBuilder("users", db_instance).EXISTS({"user_id": 1, "status": "active"})
        print(query)
        """
        where_clause = self._process_conditions(conditions)
        self.query = f"SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE {where_clause})"
        return self
    
    def SELECT(self, columns="*", aggregates=None, computed_fields=None, pivot=None, item_column="TAG_NAME", item_usage_column="VALUE"):
        """
        SELECT 쿼리를 생성합니다.

        :param columns: 선택할 열 목록 또는 "*" (기본값: 모든 열 선택)
        :param aggregates: 집계 함수 사전 (예: {"SUM": {"tags": ["tag1", "tag2"]}, "COUNT": {"tags": ["id1", "id2"]}})
        :param computed_fields: 계산된 필드 사전 (예: {"VAL": "(ITEM_VAL - PREV_ITEM_VAL)"})
        :param pivot: PIVOT 구문 (예: {"tag1": "ITEM = 'tag1'", "tag2": "ITEM = 'tag2'"})
        :param item_usage_column: PIVOT에서 사용할 컬럼 이름 (기본값: "VALUE")
        :return: self

        사용 예시:

        # 1. 단순 SELECT 쿼리 생성
        query = SQLBuilder("t_table", db_instance).SELECT(
            columns=["column1", "column2"]
        )
        print(query)

        # 2. 계산된 필드 포함 SELECT
        query = SQLBuilder("t_table", db_instance).SELECT(
            columns=["column1", "column2"],
            computed_fields={"total": "(price * quantity)"}
        )
        print(query)

        # 3. PIVOT 사용 SELECT
        query = SQLBuilder("t_table", db_instance).SELECT(
            columns=["column1"],
            pivot={"tag1": "type = 'tag1'", "tag2": "type = 'tag2'"}
        )
        print(query)

        # 4. 집계 함수 포함 SELECT
        query = SQLBuilder("t_table", db_instance).SELECT(
            columns=["column1"],
            aggregates={"SUM": {"tags": ["salary1", "salary2"]}, "COUNT": {"tags": ["id1", "id2"]}}
        )
        print(query)

        # 5. 복합 SELECT (PIVOT, 계산된 필드, 집계 모두 포함)
        query = SQLBuilder("t_table", db_instance).SELECT(
            columns=["column1"],
            computed_fields={"total": "(price * quantity)"},
            pivot={"tag1": "type = 'tag1'", "tag2": "type = 'tag2'"},
            aggregates={"SUM": {"tags": ["salary1", "salary2"]}}
        )
        print(query)
        """
        # Validate `columns`
        if not isinstance(columns, (list, str)):
            raise ValueError(f"'columns'는 리스트나 문자열이어야 합니다. 현재: {type(columns)}")

        if isinstance(columns, list):
            columns = ", ".join(columns)

        combined_clauses = []

        if pivot:
            pivot_clauses = [
                f"COALESCE(MAX(CASE WHEN {condition} THEN {item_usage_column} ELSE NULL END), 0) AS `{alias}`"
                for alias, condition in pivot.items()
            ]
            combined_clauses.extend(pivot_clauses)

        if aggregates:
            if not isinstance(aggregates, dict):
                raise ValueError(f"'aggregates'는 딕셔너리여야 합니다. 현재: {type(aggregates)}")
            for alias, aggregate_config in aggregates.items():
                if isinstance(aggregate_config, dict):  # CASE WHEN 구조
                    tags = ', '.join([f"'{tag}'" for tag in aggregate_config['tags']])
                    condition = f"{item_column} IN ({tags})"
                    combined_clauses.append(
                        f"SUM(CASE WHEN {condition} THEN {item_usage_column} ELSE 0 END) AS `{alias}`"
                    )
                else:
                    raise ValueError(f"'aggregates'는 딕셔너리여야 합니다. 현재: {type(aggregates)}")

        if computed_fields:
            for alias, field_config in computed_fields.items():
                if isinstance(field_config, dict):  # CASE WHEN 구조 지원
                    case_clauses = " ".join(
                        [f"WHEN {condition} THEN {value}" for condition, value in
                         field_config.get("conditions", {}).items()]
                    )
                    combined_clauses.append(
                        f"SUM(CASE {case_clauses} ELSE {field_config.get('default', 0)} END) AS `{alias}`"
                    )
                else:  # 일반 계산식
                    combined_clauses.append(f"{field_config} AS `{alias}`")

        if combined_clauses:
            if columns != "*":
                columns = f"{columns}, " + ", ".join(combined_clauses)
            else:
                columns = ", ".join(combined_clauses)

        self.columns = columns
        self.query = f"SELECT {self.columns} FROM {self.table_name}"
        return self

    def INSERT(self, data: dict):
        """
        INSERT 쿼리를 생성합니다.

        :param data: 삽입할 데이터 딕셔너리 (예: {"column1": "value1", "column2": "value2"})
        :return: self

        query = SQLBuilder("t_table", db_instance).INSERT(
            data={"id": 1, "name": "John Doe", "salary": 50000}
        )
        """
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        self.query = f"INSERT INTO {self.table_name} ({keys}) VALUES ({placeholders})"
        self.params = list(data.values())
        return self

    def DELETE(self, where=None):
        """
        DELETE 쿼리를 생성합니다.

        :return: self

        query = SQLBuilder("t_table", db_instance).DELETE().WHERE(
            {"id": 1}
        )
        """
        self.query = f"DELETE FROM {self.table_name}"
        
        if where:
            where_clause = self._process_conditions(where)
            self.query += f" WHERE {where_clause}"
        return self

    def WHERE(self, condition_items: dict):
        # Ensure the query starts with SELECT if not already set
        if not self.query.startswith("SELECT"):
            self.query = f"SELECT {self.columns} FROM {self.table_name}"

        condition_clauses = []
        for key, value in condition_items.items():
            if isinstance(value, tuple) and len(value) == 2:  # Operators like >, <, =
                operator, val = value
                condition_clauses.append(f"{key} {operator} %s")
                self.params.append(val)
            elif isinstance(value, list) and len(value) == 2:  # BETWEEN
                condition_clauses.append(f"{key} BETWEEN %s AND %s")
                self.params.extend(value)
            elif isinstance(value, (str, int, float)):  # Default equality
                condition_clauses.append(f"{key}=%s")
                self.params.append(value)
            else:
                raise ValueError(f"Invalid condition value for {key}: {value}")

        if condition_clauses:
            self.query += f" WHERE {' AND '.join(condition_clauses)}"
        return self

    def JOIN(self, join_type: str, table: str, on_condition: str):
        self.query += f" {join_type.upper()} JOIN {table} ON {on_condition}"
        return self

    def GROUP_BY(self, columns: list):
        self.query += f" GROUP BY {', '.join(columns)}"
        return self

    def HAVING(self, condition: str):
        self.query += f" HAVING {condition}"
        return self

    def ORDER_BY(self, columns: list):
        order_clauses = []
        for col in columns:
            if col.startswith("-"):
                order_clauses.append(f"{col[1:]} DESC")
            else:
                order_clauses.append(f"{col} ASC")
        self.query += f" ORDER BY {', '.join(order_clauses)}"
        return self

    def LIMIT(self, limit: int):
        self.query += f" LIMIT {limit}"
        return self

    def all(self):
        """
        Fetch all rows from the table.
        """
        self.query = f"SELECT {self.columns} FROM {self.table_name}"
        return self

    def order_by(self, *fields):
        """
        Add ORDER BY clause.
        Example: order_by('-age', 'name')
        """
        order_clauses = []
        for field in fields:
            if field.startswith("-"):
                order_clauses.append(f"{field[1:]} DESC")
            else:
                order_clauses.append(f"{field} ASC")
        self.query += f" ORDER BY {', '.join(order_clauses)}"
        return self

    def values(self, *fields):
        """
        Specify which fields to return.
        Example: values('name', 'age')
        """
        self.columns = ", ".join(fields)
        return self

    def limit(self, n):
        """
        Add LIMIT clause.
        """
        self.query += f" LIMIT {n}"
        return self

    def filter(self, **kwargs):
        """
        Add filtering conditions dynamically.
        Handles operators like __gte, __lte, __in, and __range.
        """
        if not self.query.startswith("SELECT"):
            self.query = f"SELECT {self.columns} FROM {self.table_name}"

        condition_clauses = []
        for key, value in kwargs.items():
            if "__" in key:  # Handle operators like __gte, __lte, __in, __range
                field, operator = key.split("__")
                if operator == "in" and isinstance(value, list):  # Handle IN operator
                    if not value:
                        condition_clauses.append(f"1=0")  # Always false condition
                    else:
                        placeholders = ", ".join(["%s"] * len(value))
                        condition_clauses.append(f"{field} IN ({placeholders})")
                        self.params.extend(value)
                elif operator == "range" and isinstance(value, list) and len(value) == 2:  # Handle RANGE operator
                    condition_clauses.append(f"{field} BETWEEN %s AND %s")
                    self.params.extend(value)
                elif operator == "like":
                    condition_clauses.append(f"{field} LIKE %s")
                    self.params.append(value)
                else:
                    sql_operator = {
                        "gte": ">=",
                        "lte": "<=",
                        "gt": ">",
                        "lt": "<",
                        "exact": "=",
                        "neq": "!=",
                        "like": "LIKE",
                    }.get(operator, "=")
                    condition_clauses.append(f"{field} {sql_operator} %s")
                    self.params.append(value)
            else:  # Default equality
                if key == 'use':
                    condition_clauses.append(f"'{key}'=%s")
                else:
                    condition_clauses.append(f"{key}=%s")
                self.params.append(value)

        if condition_clauses:
            if "WHERE" not in self.query:
                self.query += f" WHERE {' AND '.join(condition_clauses)}"
            else:
                self.query += f" AND {' AND '.join(condition_clauses)}"
        return self

    def get(self, conditions: dict):
        """
        특정 조건을 만족하는 단일 레코드를 반환.
        사용 예제:
        user = db.get({"id": 1})
        """
        condition_clauses = []
        for key, value in conditions.items():
            operator = "="
            if "__" in key:
                key, suffix = key.split("__")
                operator = {
                    "gte": ">=", "lte": "<=", "gt": ">", "lt": "<",
                    "neq": "!=", "like": "LIKE"
                }.get(suffix, "=")
            condition_clauses.append(f"{key} {operator} %s")
            self.params.append(value)
        
        where_clause = " AND ".join(condition_clauses)
        self.query = f"SELECT {self.columns} FROM {self.table_name} WHERE {where_clause} LIMIT 1"
        params = self.get_params()
        try:
            result = dict_to_object(self.db_instance.fetch_one(self.query, params))
            return result
        except Exception as e:
            self.log_query()
            sql_logger.error("Error executing query: %s", str(e))
            raise
        
    def build_query(self):
        """
        SQL 쿼리를 빌드하고 반환합니다.
        """
        if not self.query:
            self.query = f"SELECT {self.columns} FROM {self.table_name}"
        return self.query

    def execute(self):
        sql_query = self.build_query()
        params = self.get_params()

        # 실행 전 로깅

        try:
       
            if isinstance(params, tuple):
                # ✅ execute_query()는 단일 튜플을 기대함
                result = self.db_instance.execute_query(sql_query, params)
            else:
                # 🚨 데이터 타입이 올바르지 않으면 오류 발생
                self.log_query()
                raise ValueError("Invalid parameters format: expected list of tuples or a single tuple.")
            return result
        except Exception as e:
            self.log_query()
            sql_logger.error("Error executing query: %s", str(e))
            raise

    def execute_many(self):
        sql_query = self.build_query()
        params = self.get_params()

        try:
            if isinstance(params, tuple) and all(isinstance(i, tuple) for i in params):
                # ✅ execute_many() 사용
                result = self.db_instance.execute_many(sql_query, params)
                return result
            else:
                # 🚨 데이터 타입이 올바르지 않으면 오류 발생
                self.log_query()
                raise ValueError("Invalid parameters format: expected list of tuples or a single tuple.")
        except Exception as e:
            self.log_query()
            sql_logger.error("Error executing query: %s", str(e))
            raise


    def __str__(self):
        return self.query

    def get_params(self):
        return tuple(self.params)

    def bulk_create(self, data_list):
        """
        여러 개의 데이터를 한 번에 INSERT하는 기능
        :param data_list: 리스트 형식의 데이터 [{"col1": val1, "col2": val2}, ...]
        :return: self
        
        사용 예시:
        query = SQLBuilder("users", db_instance).bulk_create([
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"},
        ])
        query.execute()
        """
        if not data_list:
            raise ValueError("bulk_create: 데이터 리스트가 비어 있습니다.")

        keys = list(data_list[0].keys())
        columns = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        values = [tuple(data.values()) for data in data_list]
        
        self.query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        self.params = values
        return self

    # key_field가 리스트일 경우에도 동작하도록 수정
    def bulk_create_or_update(self, data_list, key_field):
        if not data_list:
            raise ValueError("bulk_update: 데이터 리스트가 비어 있습니다.")

        # ✅ 모든 항목이 동일한 키를 가지고 있는지 확인
        all_keys = {key for data in data_list for key in data.keys()}
        
        # key_field가 리스트인지 확인하여 처리
        if isinstance(key_field, list):
            if not set(key_field).issubset(all_keys):
                raise ValueError(f"bulk_update: key_field '{key_field}' 중 하나 이상이 데이터에 없습니다.")
            
            # 중복 검사: ITEM과 READ_DATETIME이 동시에 중복되는 경우만 허용되지 않도록 처리
            data_dict = {}
            for data in data_list:
                key_tuple = tuple(data[k] for k in key_field)
                data_dict[key_tuple] = data  # 동일한 키 값이 있으면 마지막 값으로 업데이트
            data_list = list(data_dict.values())
        
        else:
            if key_field not in all_keys:
                raise ValueError(f"bulk_update: key_field '{key_field}'가 데이터에 없습니다.")

        if not all_keys - set(key_field if isinstance(key_field, list) else [key_field]):
            raise ValueError("bulk_update: key_field 외에 업데이트할 필드가 없습니다.")

        # ✅ 업데이트할 컬럼 추출
        keys = [key for key in data_list[0].keys() if key not in (key_field if isinstance(key_field, list) else [key_field])]
        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join(["%s"] * len(data_list[0]))
        
        # ✅ ON DUPLICATE KEY UPDATE 절 생성 (기존 데이터 존재 시 업데이트 수행)
        update_clauses = ", ".join([f"{key} = VALUES({key})" for key in keys])

        # ✅ 데이터 변환
        values = [tuple(data[key] for key in data_list[0].keys()) for data in data_list]

        # ✅ MariaDB/MySQL 전용 쿼리 생성 (VALUES() 사용 가능)
        self.query = f"""
            INSERT INTO {self.table_name} ({columns}) 
            VALUES ({placeholders}) 
            ON DUPLICATE KEY UPDATE {update_clauses}
        """
        self.params = values

        return self

    def bulk_update(self, data_list, key_field):
        """
        여러 개의 데이터를 한 번에 UPDATE하는 기능
        :param table_name: 업데이트할 테이블 이름
        :param data_list: [{"id": 1, "status": "completed", "response": "..."}]
        :param key_field: 업데이트 기준이 되는 필드 (예: 'id')
        :return: 실행된 SQL 쿼리
        """
        if not data_list:
            raise ValueError("bulk_update: 데이터 리스트가 비어 있습니다.")

        # ✅ 모든 항목이 동일한 키를 가지고 있는지 확인
        all_keys = {key for data in data_list for key in data.keys()}
        if key_field not in all_keys:
            raise ValueError(f"bulk_update: key_field '{key_field}'가 데이터에 없습니다.")
        if not all_keys - {key_field}:
            raise ValueError("bulk_update: key_field 외에 업데이트할 필드가 없습니다.")

        keys = [key for key in data_list[0].keys() if key != key_field]

        # ✅ 실행할 SQL 쿼리 생성
        self.query = f"""
            UPDATE {self.table_name}
            SET {', '.join(f"{key} = %s" for key in keys)}
            WHERE {key_field} = %s;
        """

        # ✅ executemany()에 전달할 데이터 생성
        self.params = [tuple(data[key] for key in keys) + (data[key_field],) for data in data_list]

        return self
