var riverApp = angular.module('riverApp', ['ngSanitize']);

riverApp.filter('convertDate', function() {
    return function(input) {
	return Date.parse(input);
    };
});

riverApp.controller('RiverController', ['$scope', '$http', function($scope, $http) {
    $http.get('manifest.js').success(function(obj) {
	$scope.loading = true;
	$scope.rivers = obj;
	$scope.currentRiver = obj[0];
	$scope.loading = false;
    });

    $scope.$watch('currentRiver', function() {
	if ($scope.currentRiver) {
	    $scope.loading = true;
	    $http.get($scope.currentRiver.url).success(function(obj) {
		$scope.riverObj = obj;
	    });
	    $scope.loading = false;
	}
    });

    $scope.refresh = function() {
	$scope.loading = true;
	if ($scope.currentRiver) {
	    $http.get($scope.currentRiver.url).success(function(obj) {
		$scope.riverObj = obj;
	    });
	}
	$scope.loading = false;
    };
}]);
