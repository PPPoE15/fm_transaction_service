from apps.jobs.bootstrap import dramatiq

dramatiq.setup()

if __name__ == "__main__":
    from apps.jobs.bootstrap import scheduler

    scheduler.setup()
