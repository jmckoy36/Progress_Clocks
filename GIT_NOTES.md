# Git Quick Notes

## Initialize (only once per project)
git init

## Save changes (make a version)
Stage all files and save them with a message:

git add .
git commit -m "Describe change here"
### To add to GitHub
git push

## Check history
See a quick list of your commits:
git log --oneline


## Roll back to a previous version
*Careful with this — ask ChatGPT if unsure!*
git checkout <commit_id>

(Use the commit ID from `git log --oneline`)

## Tips
- Commit often, even small changes.  
- Use clear messages like `"Added Notes feature to Tug-of-War clock"`.  
- Each commit is a “restore point” you can go back to.  






