"""Initial schema: corpus, query logs, answers, feedback, index jobs/state, admin users.

Revision ID: 0001
Revises:
Create Date: 2026-10-08 13:20:54.960989
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('admin_users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_admin_users')),
    sa.UniqueConstraint('username', name=op.f('uq_admin_users_username'))
    )
    op.create_table('documents',
    sa.Column('doc_id', sa.Text(), nullable=False),
    sa.Column('lang', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('short_title', sa.Text(), nullable=False),
    sa.Column('doc_type', sa.Text(), nullable=False),
    sa.Column('number', sa.Text(), nullable=True),
    sa.Column('adopted_date', sa.Date(), nullable=True),
    sa.Column('revision_date', sa.Date(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('article_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('corpus_version', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("doc_type IN ('code', 'law', 'decree', 'resolution', 'order', 'other')", name=op.f('ck_documents_doc_type')),
    sa.CheckConstraint("lang IN ('ru', 'kk')", name=op.f('ck_documents_lang')),
    sa.CheckConstraint("status IN ('in_force', 'repealed', 'not_yet_in_force')", name=op.f('ck_documents_status')),
    sa.PrimaryKeyConstraint('doc_id', 'lang', name=op.f('pk_documents'))
    )
    op.create_index('ix_documents_lang_doc_type', 'documents', ['lang', 'doc_type'], unique=False)
    op.create_table('index_jobs',
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Text(), server_default='reindex', nullable=False),
    sa.Column('status', sa.Text(), server_default='queued', nullable=False),
    sa.Column('progress', sa.Float(), server_default='0', nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('collection', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('reindex')", name=op.f('ck_index_jobs_kind')),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f('ck_index_jobs_status')),
    sa.CheckConstraint('progress >= 0 AND progress <= 1', name=op.f('ck_index_jobs_progress')),
    sa.PrimaryKeyConstraint('job_id', name=op.f('pk_index_jobs'))
    )
    op.create_index('ix_index_jobs_created_at', 'index_jobs', ['created_at'], unique=False)
    op.create_index('uq_index_jobs_one_active', 'index_jobs', [sa.literal_column('(true)')], unique=True, postgresql_where=sa.text("status IN ('queued', 'running')"))
    op.create_table('query_logs',
    sa.Column('query_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('session_hash', sa.Text(), nullable=True),
    sa.Column('client', sa.Text(), server_default='unknown', nullable=False),
    sa.Column('ua_family', sa.Text(), nullable=True),
    sa.Column('endpoint', sa.Text(), server_default='search', nullable=False),
    sa.Column('query', sa.Text(), nullable=False),
    sa.Column('query_norm', sa.Text(), nullable=False),
    sa.Column('lang', sa.Text(), nullable=False),
    sa.Column('mode', sa.Text(), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('top_k', sa.SmallInteger(), nullable=False),
    sa.Column('result_count', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('zero_results', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('top_article_id', sa.Text(), nullable=True),
    sa.Column('total_candidates', sa.Integer(), nullable=True),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('timing_ms', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('search_ms', sa.Integer(), nullable=True),
    sa.Column('degraded', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('is_degraded', sa.Boolean(), sa.Computed('cardinality(degraded) > 0', persisted=True), nullable=False),
    sa.Column('has_answer', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('error_code', sa.Text(), nullable=True),
    sa.Column('pipeline_version', sa.Text(), nullable=True),
    sa.CheckConstraint("client IN ('web', 'api-key', 'unknown')", name=op.f('ck_query_logs_client')),
    sa.CheckConstraint("lang IN ('ru', 'kk')", name=op.f('ck_query_logs_lang')),
    sa.CheckConstraint("mode IN ('hybrid', 'semantic', 'keyword')", name=op.f('ck_query_logs_mode')),
    sa.PrimaryKeyConstraint('query_id', name=op.f('pk_query_logs'))
    )
    op.create_index('ix_query_logs_created_at', 'query_logs', ['created_at'], unique=False)
    op.create_index('ix_query_logs_degraded_created_at', 'query_logs', ['created_at'], unique=False, postgresql_where=sa.text('is_degraded'))
    op.create_index('ix_query_logs_lang_created_at', 'query_logs', ['lang', 'created_at'], unique=False)
    op.create_index('ix_query_logs_mode_created_at', 'query_logs', ['mode', 'created_at'], unique=False)
    op.create_index('ix_query_logs_query_norm', 'query_logs', ['query_norm'], unique=False)
    op.create_index('ix_query_logs_session_hash', 'query_logs', ['session_hash'], unique=False)
    op.create_index('ix_query_logs_zero_results_created_at', 'query_logs', ['created_at'], unique=False, postgresql_where=sa.text('zero_results'))
    op.create_table('answers',
    sa.Column('answer_id', sa.UUID(), nullable=False),
    sa.Column('query_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), server_default='', nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('citations', postgresql.ARRAY(sa.SmallInteger()), server_default=sa.text("'{}'::smallint[]"), nullable=False),
    sa.Column('invalid_citations_removed', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('grounded', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('finish_reason', sa.Text(), nullable=True),
    sa.Column('error_code', sa.Text(), nullable=True),
    sa.Column('search_ms', sa.Integer(), nullable=True),
    sa.Column('ttft_ms', sa.Integer(), nullable=True),
    sa.Column('total_ms', sa.Integer(), nullable=True),
    sa.Column('pipeline_version', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('completed', 'error', 'cancelled')", name=op.f('ck_answers_status')),
    sa.ForeignKeyConstraint(['query_id'], ['query_logs.query_id'], name=op.f('fk_answers_query_id_query_logs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('answer_id', name=op.f('pk_answers')),
    sa.UniqueConstraint('query_id', name=op.f('uq_answers_query_id'))
    )
    op.create_index('ix_answers_created_at', 'answers', ['created_at'], unique=False)
    op.create_table('articles',
    sa.Column('article_id', sa.Text(), nullable=False),
    sa.Column('doc_id', sa.Text(), nullable=False),
    sa.Column('lang', sa.Text(), nullable=False),
    sa.Column('unit_type', sa.Text(), nullable=False),
    sa.Column('unit_key', sa.Text(), nullable=False),
    sa.Column('unit_number', sa.Text(), nullable=True),
    sa.Column('unit_title', sa.Text(), nullable=True),
    sa.Column('unit_order', sa.Integer(), nullable=False),
    sa.Column('unit_status', sa.Text(), nullable=False),
    sa.Column('section_title', sa.Text(), nullable=True),
    sa.Column('chapter_title', sa.Text(), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('amendment_notes', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('has_amendments', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('parallel_article_id', sa.Text(), nullable=True),
    sa.Column('content_hash', sa.Text(), nullable=False),
    sa.Column('corpus_version', sa.Text(), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector(CASE WHEN lang = 'ru' THEN 'russian'::regconfig ELSE 'simple'::regconfig END, coalesce(unit_title, '')), 'A') || setweight(to_tsvector(CASE WHEN lang = 'ru' THEN 'russian'::regconfig ELSE 'simple'::regconfig END, text), 'B')", persisted=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("lang IN ('ru', 'kk')", name=op.f('ck_articles_lang')),
    sa.CheckConstraint("unit_status IN ('in_force', 'excluded')", name=op.f('ck_articles_unit_status')),
    sa.CheckConstraint("unit_type IN ('article', 'paragraph', 'chapter', 'preamble', 'annex')", name=op.f('ck_articles_unit_type')),
    sa.ForeignKeyConstraint(['doc_id', 'lang'], ['documents.doc_id', 'documents.lang'], name=op.f('fk_articles_doc_id_lang_documents'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('article_id', name=op.f('pk_articles')),
    sa.UniqueConstraint('doc_id', 'lang', 'unit_key', name=op.f('uq_articles_doc_id_lang_unit_key'))
    )
    op.create_index('ix_articles_doc_id_lang_unit_order', 'articles', ['doc_id', 'lang', 'unit_order'], unique=False)
    op.create_index('ix_articles_tsv', 'articles', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('feedback',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('query_id', sa.UUID(), nullable=False),
    sa.Column('session_hash', sa.Text(), nullable=True),
    sa.Column('target', sa.Text(), nullable=False),
    sa.Column('article_id', sa.Text(), nullable=True),
    sa.Column('rating', sa.SmallInteger(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("target <> 'result' OR article_id IS NOT NULL", name=op.f('ck_feedback_result_has_article')),
    sa.CheckConstraint("target IN ('result', 'answer')", name=op.f('ck_feedback_target')),
    sa.CheckConstraint('rating IN (1, -1)', name=op.f('ck_feedback_rating')),
    sa.ForeignKeyConstraint(['query_id'], ['query_logs.query_id'], name=op.f('fk_feedback_query_id_query_logs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feedback')),
    sa.UniqueConstraint('session_hash', 'query_id', 'target', 'article_id', name='uq_feedback_session_query_target_article', postgresql_nulls_not_distinct=True)
    )
    op.create_index('ix_feedback_created_at', 'feedback', ['created_at'], unique=False)
    op.create_index('ix_feedback_query_id', 'feedback', ['query_id'], unique=False)
    op.create_table('index_state',
    sa.Column('collection', sa.Text(), nullable=False),
    sa.Column('pipeline_version', sa.Text(), nullable=False),
    sa.Column('index_compat_id', sa.Text(), nullable=False),
    sa.Column('corpus_version', sa.Text(), nullable=True),
    sa.Column('points_count', sa.Integer(), nullable=False),
    sa.Column('documents_count', sa.Integer(), nullable=True),
    sa.Column('articles_count', sa.Integer(), nullable=True),
    sa.Column('job_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['index_jobs.job_id'], name=op.f('fk_index_state_job_id_index_jobs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('collection', name=op.f('pk_index_state'))
    )


def downgrade() -> None:
    op.drop_table('index_state')
    op.drop_index('ix_feedback_query_id', table_name='feedback')
    op.drop_index('ix_feedback_created_at', table_name='feedback')
    op.drop_table('feedback')
    op.drop_index('ix_articles_tsv', table_name='articles', postgresql_using='gin')
    op.drop_index('ix_articles_doc_id_lang_unit_order', table_name='articles')
    op.drop_table('articles')
    op.drop_index('ix_answers_created_at', table_name='answers')
    op.drop_table('answers')
    op.drop_index('ix_query_logs_zero_results_created_at', table_name='query_logs', postgresql_where=sa.text('zero_results'))
    op.drop_index('ix_query_logs_session_hash', table_name='query_logs')
    op.drop_index('ix_query_logs_query_norm', table_name='query_logs')
    op.drop_index('ix_query_logs_mode_created_at', table_name='query_logs')
    op.drop_index('ix_query_logs_lang_created_at', table_name='query_logs')
    op.drop_index('ix_query_logs_degraded_created_at', table_name='query_logs', postgresql_where=sa.text('is_degraded'))
    op.drop_index('ix_query_logs_created_at', table_name='query_logs')
    op.drop_table('query_logs')
    op.drop_index('uq_index_jobs_one_active', table_name='index_jobs', postgresql_where=sa.text("status IN ('queued', 'running')"))
    op.drop_index('ix_index_jobs_created_at', table_name='index_jobs')
    op.drop_table('index_jobs')
    op.drop_index('ix_documents_lang_doc_type', table_name='documents')
    op.drop_table('documents')
    op.drop_table('admin_users')
