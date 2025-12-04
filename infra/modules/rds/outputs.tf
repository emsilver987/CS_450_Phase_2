output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.acme_rds.endpoint
}

output "rds_address" {
  description = "RDS instance address (hostname only)"
  value       = aws_db_instance.acme_rds.address
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.acme_rds.port
}

output "rds_database" {
  description = "RDS database name"
  value       = aws_db_instance.acme_rds.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.acme_rds.username
}

output "rds_security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds_sg.id
}

