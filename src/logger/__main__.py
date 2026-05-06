from .classes.Logger import Logger


if __name__ == "__main__":
    Logger.setup("swebench", "django__django-11066")
    # print("Salut tout le monde")
    Logger.info("Salut tout le monde !")
    Logger.error("Salut tout le monde !")
    Logger.info("Salut tout le monde !")

    Logger.debug("Salut tout le monde !")
    # Logger.save_task_result({"Test": 4}, {"5": "test"})
