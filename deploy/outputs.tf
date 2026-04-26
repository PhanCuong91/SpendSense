output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ec2_instance_id" {
  value = aws_instance.app_host.id
}

output "ec2_public_ip" {
  value = aws_instance.app_host.public_ip
}

output "efs_id" {
  value = aws_efs_file_system.app_fs.id
}

output "efs_access_point" {
  value = aws_efs_access_point.ec2_ap.arn
}

output "schedule_start_cron_utc" {
  value = var.schedule_start_cron_utc
}

output "schedule_stop_cron_utc" {
  value = var.schedule_stop_cron_utc
}
