# RDS Subnet Group
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "acme-rds-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "acme-rds-subnet-group"
  }
}

# Security Group for RDS
resource "aws_security_group" "rds_sg" {
  name        = "acme-rds-sg"
  description = "Security group for ACME RDS PostgreSQL instance"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.security_group_ids
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "acme-rds-sg"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "acme_rds" {
  identifier = "acme-rds"
  engine     = "postgres"
  # engine_version omitted - AWS will use default version for the region
  instance_class        = var.db_instance_class
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = false

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = false

  skip_final_snapshot      = true
  deletion_protection      = false
  backup_retention_period  = 0
  delete_automated_backups = true

  tags = {
    Name = "acme-rds"
  }
}

# Note: Database schema will be initialized by the application on first connection
# The schema creation SQL is in src/services/rds_service.py

