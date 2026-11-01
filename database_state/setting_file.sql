create database sustainability_course_db;
create extension vector; -- pgvector

create type user_role as enum ('student', 'teacher', 'admin');
create type message_sender as enum ('user', 'ai');
create type status as enum ('on_check', 'needs_revision', 'approved');

create table users(
	id bigint generated always as identity primary key,
	email varchar(320) not null constraint uc_email unique,
	username varchar(255) not null,
	role user_role not null,
	telegram_id bigint null constraint uc_telegram_id unique
);

create table chat_sessions(
	id bigint generated always as identity primary key,
	user_id bigint not null constraint fk_user_id references users(id) on delete cascade,
	created_at timestamptz default current_timestamp
);
create index idx_user_id on chat_sessions(user_id);

create table messages(
	id bigint generated always as identity primary key,
	session_id bigint not null constraint fk_session_id references chat_sessions(id) on delete cascade,
	sender message_sender not null,
	text text not null,
	created_at timestamptz default current_timestamp
);
create index idx_session_id on messages(session_id);

create table submissions(
	id bigint generated always as identity primary key,
	student_id bigint not null constraint fk_student_id references users(id) on delete cascade,
	file text not null,
	status status not null,
	created_at timestamptz default current_timestamp
);
create index idx_student_id on submissions(student_id);

create table feedbacks(
	id bigint generated always as identity primary key,
 	text text not null unique
);
ALTER TABLE documents DROP CONSTRAINT IF EXISTS uc_doc;

create table reviews(
	id bigint generated always as identity primary key,
	submission_id bigint not null constraint fk_submission_id references submissions(id) on delete cascade,
	feedback_id bigint not null constraint fk_feedback_id references feedbacks(id) on delete cascade,
	checklist_results jsonb not null,
	created_at timestamptz default current_timestamp
);
create index idx_submission_id on reviews(submission_id);
create index idx_feedback_id on reviews(feedback_id);

create table grades(
	id bigint generated always as identity primary key,
 	student_id bigint not null constraint fk_graded_student_id references users(id) on delete cascade,
 	submission_id bigint not null constraint fk_graded_submission_id references submissions(id) on delete cascade,
 	feedback_id bigint not null constraint fk_ai_feedback_id references feedbacks(id) on delete cascade,
 	final_score numeric(5, 2) not null constraint chk_score_validity check (final_score >= 0 and final_score <= 100),
 	graded_by bigint not null constraint fk_grading_user references users(id) on delete cascade,
 	created_at timestamptz default current_timestamp
);
create index idx_graded_student_id on grades(student_id);
create index idx_graded_submission_id on grades(submission_id);
create index idx_ai_feedback_id on grades(feedback_id);
create index idx_grading_user on grades(graded_by);

create table documents(
	id bigint generated always as identity primary key,
 	text text
);
create index doc_hash on documents (md5(text));

create table document_chunks(
	id bigint generated always as identity primary key,
 	document_id bigint not null constraint fk_document_id references documents(id) on delete cascade,
 	content text,
 	category varchar(50),
 	embedding vector(1024)
);
create index idx_document_id on document_chunks(document_id);