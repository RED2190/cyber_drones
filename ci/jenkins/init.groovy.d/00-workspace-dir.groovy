// Workspace путь должен быть одинаковым внутри Jenkins-контейнера и на хосте,
// потому что Jenkins использует host docker daemon через /var/run/docker.sock.
// Иначе bind-mounts из docker-compose внутри пайплайнов получают пустые директории
// (Docker не находит исходный путь и создаёт пустышку).
import jenkins.model.Jenkins

def workspaceDir = '/tmp/drones-jenkins-workspace/${ITEM_FULLNAME}'
def jenkins = Jenkins.instance

if (jenkins.rawWorkspaceDir != workspaceDir) {
    def klass = jenkins.class
    while (klass != null && !klass.declaredFields.any { it.name == 'workspaceDir' }) {
        klass = klass.superclass
    }
    def field = klass.getDeclaredField('workspaceDir')
    field.setAccessible(true)
    field.set(jenkins, workspaceDir)
    jenkins.save()
    println "[init.groovy.d] Workspace root set to: ${workspaceDir}"
}
