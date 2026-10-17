{%- macro date_spine(start_date, end_date) -%}
    select generate_series(cast('{{ start_date }}' as date), cast('{{ end_date }}' as date), interval 1 day) as date_day
{%- endmacro -%}

{%- macro get_max_date(table, column) -%}
    (select max({{ column }}) from {{ table }})
{%- endmacro -%}
