import subprocess
import json
from sonos import play_on_sonos
from db.models import add_todo, get_todos, supabase
from utilities.activity_logger import logger

def open_garage_door():
    logger.info("Function open_garage_door triggered")
    try:
        subprocess.run(["shortcuts", "run", "HomeKit-Open-Garage-Door"], check=True)
        return "The garage door has been opened."
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in open_garage_door: {e}")
        return f"Failed to open the garage door: {e}"

def dinner_is_ready():
    logger.info("Function dinner_is_ready triggered")
    try:
        play_on_sonos("dinner is ready", room_name="Bedroom")
        return "I announced that dinner is ready."
    except Exception as e:
        logger.error(f"Error in dinner_is_ready: {e}")
        return f"Failed to play dinner is ready audio: {e}"

def get_tasks_cmd():
    logger.info("Function get_tasks_cmd triggered")
    try:
        user_id = "default_user"  # Replace with dynamic user ID as needed
        result = get_todos(user_id)
        error = getattr(result, "error", None)
        if error:
            logger.error(f"Error in get_tasks_cmd: {error.message}")
            return f"Failed to retrieve tasks: {error.message}"
        tasks = result.data
        formatted = []
        for task in tasks:
            status = "Done" if task.get("completed") else "In progress"
            formatted.append(f"{task['id']}. {task['task']} - {status}")
        return "\n".join(formatted)
    except Exception as e:
        logger.error(f"Error in get_tasks_cmd: {e}")
        return f"Error retrieving tasks: {e}"

def create_task(task: str):
    logger.info(f"Function create_task triggered with task: {task}")
    try:
        user_id = "default_user"  # Replace with dynamic user ID as needed
        result = add_todo(user_id, task)
        error = getattr(result, "error", None)
        if error:
            logger.error(f"Error in create_task: {error.message}")
            return f"Failed to create task: {error.message}"
        return f"Task '{task}' created successfully."
    except Exception as e:
        logger.error(f"Error in create_task: {e}")
        return f"Error creating task: {e}"

def mark_task_done(task: str):
    logger.info(f"Function mark_task_done triggered with task description: {task}")
    try:
        user_id = "default_user"  # Replace with dynamic user ID as needed
        # Look for tasks whose description contains the provided snippet (case-insensitive)
        tasks_result = supabase.table("todos") \
            .select("*") \
            .eq("user_id", user_id) \
            .ilike("task", f"%{task}%") \
            .execute()
        if tasks_result.error or not tasks_result.data:
            logger.error(f"No task found matching '{task}'.")
            return f"No task found matching '{task}'."
        
        # Filter out already completed tasks
        matching_tasks = [t for t in tasks_result.data if not t.get("completed")]
        if not matching_tasks:
            return f"All tasks matching '{task}' are already marked as done."
        if len(matching_tasks) > 1:
            tasks_summary = ", ".join([t["task"] for t in matching_tasks])
            return f"Multiple tasks match '{task}': {tasks_summary}. Please specify which one to mark as done."
        
        task_to_update = matching_tasks[0]
        result = supabase.table("todos") \
            .update({"completed": True}) \
            .eq("id", task_to_update["id"]) \
            .eq("user_id", user_id) \
            .execute()
            
        if result.error:
            logger.error(f"Error in mark_task_done: {result.error.message}")
            return f"Failed to mark task '{task_to_update['task']}' as done: {result.error.message}"
            
        # Check if any rows were updated
        if not result.data:
            logger.error(f"Update returned no rows for task id {task_to_update['id']}.")
            return f"Failed to mark task '{task_to_update['task']}' as done; no rows were updated."

        # Log additional details about the task that was marked complete
        logger.info(f"Task marked as complete: ID {task_to_update['id']}, Task '{task_to_update['task']}', Result Data: {result.data}")

        return f"Task '{task_to_update['task']}' marked as done. Cheers, sir!"
    except Exception as e:
        logger.error(f"Error in mark_task_done: {e}")
        return f"Error marking task as done: {e}"

AVAILABLE_FUNCTIONS = {
    "open_garage_door": open_garage_door,
    "get_tasks": get_tasks_cmd,
    "create_task": create_task,
    "mark_task_done": mark_task_done,
}

def dispatch_function_call(function_call):
    logger.info(f"Dispatching function call: {function_call}")
    fname = function_call.get("name")
    fn = AVAILABLE_FUNCTIONS.get(fname)
    if not fn:
        logger.error(f"Function '{fname}' is not implemented.")
        return f"Function '{fname}' is not implemented."
    arguments = function_call.get("arguments")
    try:
        args = json.loads(arguments) if arguments else {}
    except Exception as e:
        logger.error(f"Error parsing arguments for {fname}: {e}")
        args = {}
    try:
        return fn(**args) if args else fn()
    except Exception as e:
        logger.error(f"Error during function call {fname}: {e}")
        return f"Error executing function '{fname}': {e}"