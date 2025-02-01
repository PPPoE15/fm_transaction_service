from modules.jobs.bootstrap import dramatiq

dramatiq.setup()

if __name__ == "__main__":
    from modules.jobs.bootstrap import scheduler

    scheduler.setup()
